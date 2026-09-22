#!/usr/bin/env python3
"""Scheduled Snowflake refresh - the "reliable, authenticated way for the
deployed app to receive refreshed data" that doesn't depend on anyone's
open Claude chat, a laptop folder, or manual JSON edits.

Run on a schedule (see .github/workflows/refresh_snowflake.yml) or by hand.
Pulls the last REFRESH_WEEKS weeks of in-app reviews & feedback from
JEENY_PROD.GENERAL.FEEDBACKEVENTS (via modules/snowflake_client.py - the
exact same validated, aggregate-only, PII-free queries the live app uses)
and writes data/sentiment_summary.json + data/sentiment_themes.json, which
is what the app falls back to reading whenever it has no direct Snowflake
access of its own (e.g. most local `streamlit run` sessions).

Credentials come from environment variables, never from a committed file:
    SNOWFLAKE_ACCOUNT     required
    SNOWFLAKE_USER        required
    SNOWFLAKE_PASSWORD    required (or SNOWFLAKE_PRIVATE_KEY_PATH for key-pair auth)
    SNOWFLAKE_ROLE        optional, defaults to ROLE_MARKET_INTELLIGENCE
    SNOWFLAKE_WAREHOUSE   optional, defaults to COMPUTE_WH

Safety: if the Snowflake fetch fails outright (bad creds, network,
warehouse suspended), this script leaves the existing data/*.json files
untouched and exits non-zero, so a transient outage never wipes out the
last known good data - it just means the site goes a cycle without a
fresher refresh, which get_refresh_state() surfaces in the UI as a stale
"last successful refresh" time rather than silently going empty.

Deduplication: every write is a full recompute of the requested week
window straight from Snowflake's own aggregates (GROUP BY, not an
incremental append), so re-running this script never double-counts -
it's naturally idempotent. GUID-level dedup happens inside Snowflake's
COUNT/COUNT DISTINCT semantics before any row reaches this script.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modules import data_loader, refresh_state, snowflake_client  # noqa: E402

REFRESH_WEEKS = 10  # a bit more than the 6-week trend the UI shows, for headroom

DATA_DIR = REPO_ROOT / "data"
SUMMARY_PATH = DATA_DIR / "sentiment_summary.json"
THEMES_PATH = DATA_DIR / "sentiment_themes.json"


def _credentials_from_env() -> dict[str, str] | None:
    account = os.environ.get("SNOWFLAKE_ACCOUNT")
    user = os.environ.get("SNOWFLAKE_USER")
    password = os.environ.get("SNOWFLAKE_PASSWORD")
    if not account or not user or not password:
        return None
    return {
        "account": account,
        "user": user,
        "password": password,
        "role": os.environ.get("SNOWFLAKE_ROLE", "ROLE_MARKET_INTELLIGENCE"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        "login_timeout": 15,
    }


def _atomic_write_json(path: Path, data) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)  # atomic on POSIX and Windows
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def main() -> int:
    creds = _credentials_from_env()
    if creds is None:
        msg = "Missing SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PASSWORD environment variables"
        print(f"ERROR: {msg}", file=sys.stderr)
        refresh_state.record_refresh("snowflake", "error", msg)
        return 1

    weeks = data_loader.load_weeks()
    window = weeks[-REFRESH_WEEKS:]
    range_start = data_loader.date.fromisoformat(window[0]["id"])
    range_end_inclusive = data_loader.date.fromisoformat(window[-1]["id"]) + data_loader.timedelta(days=6)
    print(f"Refreshing {window[0]['id']} .. {window[-1]['id']} ({len(window)} weeks)")

    summary_rows, error = snowflake_client.fetch_review_summary_range(range_start, range_end_inclusive, credentials=creds)
    if error is not None:
        print(f"ERROR fetching review summary: {error}", file=sys.stderr)
        refresh_state.record_refresh("snowflake", "error", error)
        return 1

    theme_rows, error = snowflake_client.fetch_theme_counts_range(range_start, range_end_inclusive, credentials=creds)
    if error is not None:
        print(f"ERROR fetching theme counts: {error}", file=sys.stderr)
        refresh_state.record_refresh("snowflake", "error", error)
        return 1

    print(f"Fetched {len(summary_rows)} summary rows, {len(theme_rows)} theme rows from Snowflake")

    # Reshape into the app's data/sentiment_summary.json + sentiment_themes.json
    # row shape (one row per week_id/cohort), matching COHORT_AUDIENCE/COHORT_MARKET.
    out_summary = []
    out_themes = []
    for w in window:
        w_start = data_loader.date.fromisoformat(w["id"])
        for cohort in data_loader.COHORTS:
            audience = data_loader.COHORT_AUDIENCE[cohort]
            market = data_loader.COHORT_MARKET[cohort]

            summary_row = next(
                (r for r in summary_rows if r["WEEK_START"] == w_start and r["AUDIENCE"] == audience and r["MARKET"] == market),
                None,
            )
            if summary_row is not None:
                avg_rating = summary_row.get("AVG_RATING")
                latest_event = summary_row.get("LATEST_EVENT_AT")
                out_summary.append(
                    {
                        "week_id": w["id"],
                        "cohort": cohort,
                        "item_count": summary_row.get("THEMED_ITEMS") or 0,
                        "rating": round(float(avg_rating), 2) if avg_rating is not None else None,
                        "rating_count": summary_row.get("RATED_ITEMS") or 0,
                        "positive_count": summary_row.get("POSITIVE_COUNT"),
                        "neutral_count": summary_row.get("NEUTRAL_COUNT"),
                        "negative_count": summary_row.get("NEGATIVE_COUNT"),
                        "source": "Jeeny in-app ratings & categorized feedback (Snowflake)",
                        "last_updated": latest_event.date().isoformat() if hasattr(latest_event, "date") else None,
                    }
                )

            for r in theme_rows:
                if r["WEEK_START"] == w_start and r["AUDIENCE"] == audience and r["MARKET"] == market:
                    out_themes.append(
                        {
                            "week_id": w["id"],
                            "cohort": cohort,
                            "theme": r["THEME"],
                            "mentions": r["MENTIONS"],
                        }
                    )

    # Validate before writing: every row must have the required fields and
    # sane types. A malformed row here means a real bug (a schema change
    # upstream, a bad CASE mapping) - better to fail the run loudly than
    # publish bad numbers.
    for row in out_summary:
        assert isinstance(row["item_count"], int), f"item_count not an int: {row}"
    for row in out_themes:
        assert isinstance(row["mentions"], int), f"mentions not an int: {row}"

    _atomic_write_json(SUMMARY_PATH, out_summary)
    _atomic_write_json(THEMES_PATH, out_themes)
    print(f"Wrote {len(out_summary)} summary rows and {len(out_themes)} theme rows")

    refresh_state.record_refresh("snowflake", "ok", rows_written=len(out_summary) + len(out_themes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
