#!/usr/bin/env python3
"""Scheduled Drive sync - the "hub checks that shared location
automatically" half of the publishing pipeline. The other half is
whatever writes files into the Drive folder in the first place (a
Claude chat/Cowork task with the Drive connector enabled and the
"Publish to Insights Hub" instruction added to its prompt - see
docs/PUBLISH_TO_INSIGHTS_HUB.md - or scripts/run_*.py for Snowflake-only
workflows that skip Drive entirely and write straight into
dashboard_files/runs/).

Run on a schedule (see .github/workflows/sync_drive_runs.yml) or by hand.
Mirrors every file under the configured Drive folder into
dashboard_files/runs/ (modules/drive_client.sync_folder), then lets
modules/register.discover_runs() validate what landed - a manifest
missing a required field, pointing at a missing file, or reusing another
run's run_id never gets treated as published; it just doesn't show up,
same as any other invalid run.

Credentials come from environment variables, never from a committed file:
    GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON   required - the full service-account key JSON, as one string
    GOOGLE_DRIVE_FOLDER_ID              required - the shared folder's Drive id

Safety: if the Drive connection fails outright (bad credentials, folder
not shared with the service account, network), this script changes
nothing on disk and exits non-zero - existing runs stay exactly as they
were, so a transient outage never removes something that was already
published.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modules import drive_client, refresh_state, register  # noqa: E402


def main() -> int:
    creds = drive_client.credentials_from_env()
    folder_id = drive_client.folder_id_from_env()
    if creds is None or not folder_id:
        msg = "Missing GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON / GOOGLE_DRIVE_FOLDER_ID environment variables"
        print(f"ERROR: {msg}", file=sys.stderr)
        refresh_state.record_refresh("drive", "error", msg)
        return 1

    ok, error = drive_client.check_connection(folder_id, credentials=creds)
    if not ok:
        print(f"ERROR: cannot access Drive folder {folder_id}: {error}", file=sys.stderr)
        print(
            "This usually means the folder has not been shared with the service "
            "account's email yet - see README.md 'Connecting real data sources'.",
            file=sys.stderr,
        )
        refresh_state.record_refresh("drive", "error", str(error))
        return 1

    summary, error = drive_client.sync_folder(folder_id, register.RUNS_DIR, credentials=creds)
    if summary is None:
        print(f"ERROR syncing Drive folder: {error}", file=sys.stderr)
        refresh_state.record_refresh("drive", "error", error)
        return 1

    print(f"Downloaded {len(summary['downloaded'])} file(s) from Drive")
    for path in summary["downloaded"]:
        print(f"  {path}")
    if summary["skipped_native"]:
        print(f"Skipped {len(summary['skipped_native'])} native Google Docs/Slides file(s) (need to be exported first):")
        for path in summary["skipped_native"]:
            print(f"  {path}")
    if summary["errors"]:
        print(f"{len(summary['errors'])} file(s) failed to download:", file=sys.stderr)
        for err in summary["errors"]:
            print(f"  {err}", file=sys.stderr)

    discovered = register.discover_runs()
    print(f"Registry now has {len(discovered['published'])} published run(s), {len(discovered['needs_review'])} needing review")
    for row in discovered["needs_review"]:
        print(f"  NEEDS REVIEW: {row['file']}: {row['reason']}")

    if summary["errors"] and not summary["downloaded"]:
        # Every file failed - treat the whole sync as failed, not a
        # silent partial success.
        refresh_state.record_refresh("drive", "error", "; ".join(summary["errors"][:5]))
        return 1

    refresh_state.record_refresh("drive", "ok", rows_written=len(summary["downloaded"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
