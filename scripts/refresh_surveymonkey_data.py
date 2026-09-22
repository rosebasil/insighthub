#!/usr/bin/env python3
"""Discover SurveyMonkey surveys and register new ones as drafts.

NOT VERIFIED against a real account - see the warning at the top of
modules/surveymonkey_client.py. This script is ready to run the moment
SURVEYMONKEY_ACCESS_TOKEN is set, but the first real run should be
treated as a test, not a production cutover.

What it does:
    1. List every survey visible to the token (modules/surveymonkey_client
       .list_surveys()).
    2. For any SurveyMonkey survey ID not already present in
       data/surveys.json, append a *draft* row: source="surveymonkey",
       status="draft", week_id=null, dashboard_id=null. A draft never
       shows in the Home page's survey tracker (see
       modules.data_loader.load_surveys, which only returns
       status=="published" rows) until a human sets its week_id and
       links it to a study/dashboard - "show real results only after
       their study and reporting period can be identified", per spec.
    3. For surveys already known (matched by surveymonkey_id), refresh
       `responses` from the authoritative per-survey response_count so
       published trackers stay current without a manual edit.

Deduplication: matched by SurveyMonkey's own numeric survey ID
(surveymonkey_id), which is stable and unique - never by name, since two
surveys can share a title.

Credentials: SURVEYMONKEY_ACCESS_TOKEN environment variable.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modules import refresh_state, surveymonkey_client  # noqa: E402

SURVEYS_PATH = REPO_ROOT / "data" / "surveys.json"


def _atomic_write_json(path: Path, data) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def main() -> int:
    token = os.environ.get("SURVEYMONKEY_ACCESS_TOKEN")
    if not token:
        msg = "Missing SURVEYMONKEY_ACCESS_TOKEN environment variable"
        print(f"ERROR: {msg}", file=sys.stderr)
        refresh_state.record_refresh("surveymonkey", "error", msg)
        return 1

    surveys_remote, error = surveymonkey_client.list_surveys(access_token=token)
    if error is not None:
        print(f"ERROR listing surveys: {error}", file=sys.stderr)
        refresh_state.record_refresh("surveymonkey", "error", error)
        return 1
    print(f"SurveyMonkey account has {len(surveys_remote)} surveys visible to this token")

    with open(SURVEYS_PATH, "r", encoding="utf-8") as f:
        known = json.load(f)
    known_by_smid = {row["surveymonkey_id"]: row for row in known if row.get("surveymonkey_id")}

    new_drafts = 0
    refreshed = 0
    for remote in surveys_remote:
        smid = str(remote["id"])
        if smid in known_by_smid:
            count, count_error = surveymonkey_client.get_response_count(smid, access_token=token)
            if count_error is None and count is not None:
                known_by_smid[smid]["responses"] = count
                refreshed += 1
            continue

        # New survey - register as a draft. A human must set week_id and
        # dashboard_id before it shows anywhere in the app.
        known.append(
            {
                "id": f"sv-sm-{smid}",
                "name": remote.get("title") or remote.get("nickname") or f"SurveyMonkey survey {smid}",
                "week_id": None,
                "sent": None,
                "responses": remote.get("response_count"),
                "dashboard_id": None,
                "source": "surveymonkey",
                "surveymonkey_id": smid,
                "status": "draft",
            }
        )
        new_drafts += 1

    _atomic_write_json(SURVEYS_PATH, known)
    print(f"Registered {new_drafts} new draft survey(s); refreshed response counts for {refreshed}")

    refresh_state.record_refresh("surveymonkey", "ok", rows_written=new_drafts + refreshed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
