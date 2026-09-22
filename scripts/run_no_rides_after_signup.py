#!/usr/bin/env python3
"""Scheduled biweekly run: No Rides After Sign-Up (Passengers).

Business definition - confirmed with the hub's owner on 2026-09-22, not
invented (see modules/snowflake_client.py's docstring above
fetch_no_rides_after_signup for the exact confirmation):
    passengers only; signup = SIGNUPDATE; first ride = FIRSTRIDE (a
    completed ride, not a request); window = 14 days; a period only
    counts once every signup in it has had its full 14-day window
    elapse (modules/register.is_period_ready()).

Run on a schedule (see .github/workflows/run_no_rides_after_signup.yml)
or by hand. Finds the most recent biweekly Sunday-Saturday-pair period
that is actually ready (see above), queries Snowflake for it, builds a
self-contained HTML dashboard, and publishes it through
modules/register.save_run() - the same "Publish to Insights Hub" path a
Claude chat's Drive upload also feeds into, so this run shows up in the
Studies Library exactly like any other.

Credentials: SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PASSWORD
(+ optional SNOWFLAKE_ROLE / SNOWFLAKE_WAREHOUSE) environment variables -
same as scripts/refresh_snowflake_data.py.

Idempotent: run_id encodes the period, so re-running the same period
overwrites that run's files/manifest (a revision, via save_run's
files-then-manifest write order) rather than creating a duplicate.
"""

from __future__ import annotations

import html
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modules import refresh_state, register, snowflake_client  # noqa: E402

WORKFLOW_ID = "wf-no-rides-after-signup"


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


def _most_recent_sunday(day: date) -> date:
    return day - timedelta(days=(day.weekday() + 1) % 7)


def latest_ready_period(as_of: date | None = None) -> tuple[date, date]:
    """Most recent Sunday-anchored 2-week period whose full 14-day
    window has elapsed as of `as_of` (default: today)."""
    as_of = as_of or date.today()
    period_end = _most_recent_sunday(as_of) - timedelta(days=1)  # last Saturday
    period_start = period_end - timedelta(days=13)
    while not register.is_period_ready(period_end, snowflake_client.NO_RIDES_WINDOW_DAYS, as_of):
        period_end -= timedelta(days=14)
        period_start -= timedelta(days=14)
    return period_start, period_end


def build_dashboard_html(rows: list[dict], period_start: date, period_end: date, data_as_of: str) -> str:
    body_rows = ""
    total_signups = total_no_ride = 0
    for row in sorted(rows, key=lambda r: r.get("MARKET") or ""):
        if not row.get("MARKET"):
            continue
        signups = row["SIGNUPS"]
        no_ride = row["NO_RIDE_COUNT"]
        rode = row["RODE_WITHIN_WINDOW_COUNT"]
        total_signups += signups
        total_no_ride += no_ride
        pct = f"{no_ride / signups * 100:.1f}%" if signups else "-"
        body_rows += f"""
        <tr>
          <td>{html.escape(row['MARKET'])}</td>
          <td>{signups:,}</td>
          <td>{no_ride:,}</td>
          <td>{pct}</td>
          <td>{rode:,}</td>
        </tr>"""
    overall_pct = f"{total_no_ride / total_signups * 100:.1f}%" if total_signups else "-"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>No Rides After Sign-Up - {period_start.isoformat()} to {period_end.isoformat()}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 32px; background: #F7F7F9; color: #1A1347; }}
  h1 {{ color: #662D91; font-size: 22px; margin-bottom: 4px; }}
  .caption {{ color: #6B6B76; font-size: 13px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  th, td {{ padding: 12px 16px; text-align: left; font-size: 14px; }}
  th {{ background: #662D91; color: #fff; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }}
  tr:nth-child(even) {{ background: #FAFAFC; }}
  tfoot td {{ font-weight: 700; border-top: 2px solid #662D91; }}
  .note {{ margin-top: 20px; font-size: 12px; color: #A7A9AC; }}
</style>
</head>
<body>
  <h1>No Rides After Sign-Up - Passengers</h1>
  <div class="caption">
    Period {period_start.isoformat()} to {period_end.isoformat()} &middot;
    Data as of {html.escape(data_as_of)} &middot;
    Source: JEENY_PROD.PASSENGERS.VPASSENGERSPROFILE (Snowflake)
  </div>
  <table>
    <thead>
      <tr><th>Market</th><th>Signups</th><th>No ride (14d)</th><th>No-ride rate</th><th>Rode within 14d</th></tr>
    </thead>
    <tbody>{body_rows}
    </tbody>
    <tfoot>
      <tr><td>All markets</td><td>{total_signups:,}</td><td>{total_no_ride:,}</td><td>{overall_pct}</td><td>{total_signups - total_no_ride:,}</td></tr>
    </tfoot>
  </table>
  <div class="note">
    Definition: a passenger counts as "no ride" if FIRSTRIDE is still null 14 days after SIGNUPDATE.
    Excludes test accounts (ISTEST). Markets: KSA and Jordan only (PHONECOUNTRYCODE SA/JO).
    Aggregate counts only - no passenger-level data is included in this report.
  </div>
</body>
</html>
"""


def main() -> int:
    creds = _credentials_from_env()
    if creds is None:
        msg = "Missing SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PASSWORD environment variables"
        print(f"ERROR: {msg}", file=sys.stderr)
        refresh_state.record_refresh("snowflake_no_rides", "error", msg)
        return 1

    period_start, period_end = latest_ready_period()
    print(f"Latest ready biweekly period: {period_start.isoformat()} to {period_end.isoformat()}")

    rows, error = snowflake_client.fetch_no_rides_after_signup(period_start, period_end, credentials=creds)
    if error is not None:
        print(f"ERROR fetching no-rides data: {error}", file=sys.stderr)
        refresh_state.record_refresh("snowflake_no_rides", "error", error)
        return 1

    data_as_of = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dashboard_html = build_dashboard_html(rows, period_start, period_end, data_as_of)
    run_id = f"{WORKFLOW_ID}-{period_start.isoformat()}"

    ok, save_error = register.save_run(
        workflow_id=WORKFLOW_ID,
        run_id=run_id,
        manifest_fields={
            "topic": "No Rides After Sign-Up (Passengers)",
            "source": "Snowflake",
            "owner": "rose.alnirab@jeeny.me",
            "cadence": "biweekly",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "market": "All",
            "audience": "Passenger",
            "data_as_of": data_as_of,
            "output_formats": ["dashboard_html"],
            "version": 1,
            "source_references": [snowflake_client.NO_RIDES_TABLE],
            "status": "published",
            "generated_at": data_as_of,
            "generated_by": "scripts/run_no_rides_after_signup.py",
        },
        file_payloads=[
            {"format": "dashboard_html", "filename": f"{run_id}.html", "content": dashboard_html.encode("utf-8")}
        ],
    )
    if not ok:
        print(f"ERROR saving run: {save_error}", file=sys.stderr)
        refresh_state.record_refresh("snowflake_no_rides", "error", f"no-rides run save failed: {save_error}")
        return 1

    print(f"Published run {run_id}")
    refresh_state.record_refresh("snowflake_no_rides", "ok", rows_written=len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
