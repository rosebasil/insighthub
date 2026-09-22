#!/usr/bin/env python3
"""Scheduled biweekly run: Driver & Passenger In-App Reviews report.

This is the archival/downloadable counterpart to the live "In-app
reviews & feedback" section on Home (modules/data_loader.load_review_feedback,
which shows a rolling 6-week trend per cohort). This script instead
snapshots one biweekly period into a standalone HTML report and
publishes it through modules/register.save_run(), so the topic shows up
in the Studies Library's topic -> runs -> files hierarchy with a
concrete file per period, the same as every other workflow.

Uses the exact same validated, aggregate-only Snowflake queries as the
live Home page (modules/snowflake_client.fetch_review_summary_range /
fetch_theme_counts_range) - not a separate query, so the two never
disagree about what "real" means.

Credentials: SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PASSWORD
(+ optional SNOWFLAKE_ROLE / SNOWFLAKE_WAREHOUSE) - same as
scripts/refresh_snowflake_data.py.
"""

from __future__ import annotations

import html
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modules import data_loader, refresh_state, register, snowflake_client  # noqa: E402

WORKFLOW_ID = "wf-in-app-reviews"


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


def latest_complete_biweekly_period(as_of: date | None = None) -> tuple[date, date]:
    """Most recent pair of fully-elapsed Sunday-Saturday weeks."""
    as_of = as_of or date.today()
    current_id = data_loader.current_week_id(as_of)
    prev1 = data_loader.previous_week_id(current_id)
    prev2 = data_loader.previous_week_id(prev1) if prev1 else None
    if prev1 is None or prev2 is None:
        raise RuntimeError("not enough week history to form a biweekly period")
    start2, _ = data_loader.week_bounds(prev2)
    _, end1 = data_loader.week_bounds(prev1)
    return start2, end1


def build_report_html(summary_rows: list[dict], theme_rows: list[dict], period_start: date, period_end: date, data_as_of: str) -> str:
    cohort_rows = ""
    for cohort in data_loader.COHORTS:
        rows = [r for r in summary_rows if r["cohort"] == cohort]
        item_count = sum(r["item_count"] for r in rows)
        ratings = [r["rating"] for r in rows if r.get("rating") is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
        rating_txt = f"{avg_rating:.2f} ★" if avg_rating is not None else "—"
        cohort_rows += f"""
        <tr>
          <td>{html.escape(data_loader.COHORT_LABELS[cohort])}</td>
          <td>{item_count:,}</td>
          <td>{rating_txt}</td>
        </tr>"""

    theme_totals: dict[str, int] = {}
    for r in theme_rows:
        theme_totals[r["theme"]] = theme_totals.get(r["theme"], 0) + r["mentions"]
    top_themes = sorted(theme_totals.items(), key=lambda kv: kv[1], reverse=True)[:8]
    theme_rows_html = "".join(f"<tr><td>{html.escape(t)}</td><td>{m:,}</td></tr>" for t, m in top_themes)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>In-App Reviews - {period_start.isoformat()} to {period_end.isoformat()}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 32px; background: #F7F7F9; color: #1A1347; }}
  h1 {{ color: #662D91; font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: #1A1347; font-size: 15px; margin-top: 28px; }}
  .caption {{ color: #6B6B76; font-size: 13px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  th, td {{ padding: 10px 16px; text-align: left; font-size: 14px; }}
  th {{ background: #662D91; color: #fff; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }}
  tr:nth-child(even) {{ background: #FAFAFC; }}
  .note {{ margin-top: 20px; font-size: 12px; color: #A7A9AC; }}
</style>
</head>
<body>
  <h1>Driver &amp; Passenger In-App Reviews</h1>
  <div class="caption">
    Period {period_start.isoformat()} to {period_end.isoformat()} &middot;
    Data as of {html.escape(data_as_of)} &middot;
    Source: JEENY_PROD.GENERAL.FEEDBACKEVENTS (Snowflake) - in-app ratings &amp; categorized feedback, not app-store or social-media data
  </div>
  <h2>By cohort</h2>
  <table>
    <thead><tr><th>Cohort</th><th>Themed feedback items</th><th>Avg. rating</th></tr></thead>
    <tbody>{cohort_rows}</tbody>
  </table>
  <h2>Top themes (all cohorts)</h2>
  <table>
    <thead><tr><th>Theme</th><th>Mentions</th></tr></thead>
    <tbody>{theme_rows_html}</tbody>
  </table>
  <div class="note">
    Aggregate counts only - no review text or personal identifier is included in this report.
  </div>
</body>
</html>
"""


def main() -> int:
    creds = _credentials_from_env()
    if creds is None:
        msg = "Missing SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PASSWORD environment variables"
        print(f"ERROR: {msg}", file=sys.stderr)
        refresh_state.record_refresh("snowflake", "error", msg)
        return 1

    period_start, period_end = latest_complete_biweekly_period()
    print(f"Latest complete biweekly period: {period_start.isoformat()} to {period_end.isoformat()}")

    summary_rows_raw, error = snowflake_client.fetch_review_summary_range(period_start, period_end, credentials=creds)
    if error is not None:
        print(f"ERROR fetching review summary: {error}", file=sys.stderr)
        refresh_state.record_refresh("snowflake", "error", error)
        return 1
    theme_rows_raw, error = snowflake_client.fetch_theme_counts_range(period_start, period_end, credentials=creds)
    if error is not None:
        print(f"ERROR fetching theme counts: {error}", file=sys.stderr)
        refresh_state.record_refresh("snowflake", "error", error)
        return 1

    summary_rows = []
    theme_rows = []
    for cohort in data_loader.COHORTS:
        audience = data_loader.COHORT_AUDIENCE[cohort]
        market = data_loader.COHORT_MARKET[cohort]
        for r in summary_rows_raw:
            if r["AUDIENCE"] == audience and r["MARKET"] == market:
                summary_rows.append({"cohort": cohort, "item_count": r.get("THEMED_ITEMS") or 0, "rating": r.get("AVG_RATING")})
        for r in theme_rows_raw:
            if r["AUDIENCE"] == audience and r["MARKET"] == market:
                theme_rows.append({"cohort": cohort, "theme": r["THEME"], "mentions": r["MENTIONS"]})

    data_as_of = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report_html = build_report_html(summary_rows, theme_rows, period_start, period_end, data_as_of)
    run_id = f"{WORKFLOW_ID}-{period_start.isoformat()}"

    ok, save_error = register.save_run(
        workflow_id=WORKFLOW_ID,
        run_id=run_id,
        manifest_fields={
            "topic": "Driver & Passenger In-App Reviews",
            "source": "Snowflake",
            "owner": "rose.alnirab@jeeny.me",
            "cadence": "biweekly",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "market": "All",
            "audience": "All",
            "data_as_of": data_as_of,
            "output_formats": ["dashboard_html"],
            "version": 1,
            "source_references": [snowflake_client.FEEDBACK_TABLE],
            "status": "published",
            "generated_at": data_as_of,
            "generated_by": "scripts/run_in_app_reviews_report.py",
        },
        file_payloads=[{"format": "dashboard_html", "filename": f"{run_id}.html", "content": report_html.encode("utf-8")}],
    )
    if not ok:
        print(f"ERROR saving run: {save_error}", file=sys.stderr)
        refresh_state.record_refresh("snowflake", "error", f"in-app-reviews run save failed: {save_error}")
        return 1

    print(f"Published run {run_id}")
    refresh_state.record_refresh("snowflake", "ok", rows_written=len(summary_rows) + len(theme_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
