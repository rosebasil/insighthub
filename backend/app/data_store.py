"""In-memory data store for InsightHub, loaded once from the mock JSON files
under backend/app/data/. Swap this module out for a real database or
warehouse query layer later without changing the API routes.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _load(filename: str):
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


weeks = _load("weeks.json")
dashboards = _load("dashboards.json")
studies = _load("studies.json")
highlights = _load("highlights.json")
surveys = _load("surveys.json")
issues = _load("issues.json")
performance = _load("performance.json")

weeks_by_id = {w["id"]: w for w in weeks}
dashboards_by_id = {d["id"]: d for d in dashboards}


def current_week_id() -> str:
    for w in weeks:
        if w.get("is_current"):
            return w["id"]
    return weeks[-1]["id"]


def get_week_or_404(week_id: str):
    return weeks_by_id.get(week_id)


def studies_for_week(week_id: str):
    return [s for s in studies if s["week_id"] == week_id]


def issues_for_week(week_id: str):
    return [i for i in issues if i["week_id"] == week_id]


def surveys_for_week(week_id: str):
    return [s for s in surveys if s["week_id"] == week_id]


def highlights_for_week(week_id: str):
    result = {}
    for h in highlights:
        if h["week_id"] == week_id:
            result[h["cohort"]] = h["bullets"]
    return result


def performance_for_week(week_id: str):
    rows = [r for r in performance["rows"] if r["week_id"] == week_id]
    meta = performance["meta"].get(week_id, {"cities_live": 0, "cities_total": 0})
    return {"meta": meta, "rows": rows}


def issue_status_counts(week_issues):
    counts = {"New": 0, "Under review": 0, "Reported out": 0, "Closed": 0}
    for i in week_issues:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return counts
