"""Data access layer for Jeeny Insights Hub.

Every page imports data through this module instead of reading files
directly. That means the *only* thing that needs to change when we move
from local JSON files to Snowflake, SurveyMonkey, or Power BI is the
implementation of the functions below -- page code stays the same.

Current state (MVP):
    Studies, dashboards, and the weekly summary are read from the JSON
    files in /data. This is the "sample data source" referenced in the
    project brief and is intentionally isolated behind get_* functions.

Planned automation (v2+):
    - load_studies_from_snowflake()
    - load_responses_from_surveymonkey()
    - load_dashboard_metadata_from_powerbi()
    - load_studies_from_uploaded_csv()
    - classify_text() / summarize_text()  (NLP automation placeholders)

None of the placeholder functions below are wired up yet. They exist so
the next engineer can implement one function at a time without touching
Streamlit page code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DASHBOARD_FILES_DIR = BASE_DIR / "dashboard_files"

STUDIES_PATH = DATA_DIR / "studies.json"
DASHBOARDS_PATH = DATA_DIR / "dashboards.json"
WEEKS_PATH = DATA_DIR / "weeks.json"
HIGHLIGHTS_PATH = DATA_DIR / "highlights.json"
SURVEYS_PATH = DATA_DIR / "surveys.json"
ISSUES_PATH = DATA_DIR / "issues.json"
MSU_DIF_PATH = DATA_DIR / "msu_dif_performance.json"
WEEKLY_DIGEST_PATH = DATA_DIR / "weekly_digest.json"

ISSUE_STATUSES = ["New", "Under review", "Reported out", "Closed"]
COHORTS = ["DX_KSA", "DX_JOR", "PAX_KSA", "PAX_JOR"]
COHORT_LABELS = {
    "DX_KSA": "DX · KSA",
    "DX_JOR": "DX · Jordan",
    "PAX_KSA": "PAX · KSA",
    "PAX_JOR": "PAX · Jordan",
}


# --------------------------------------------------------------------------
# Current sample-data-backed loaders (used by the app today)
# --------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_studies() -> list[dict[str, Any]]:
    """Return all studies. Currently reads data/studies.json.

    To add a new study today: append an object to data/studies.json
    following the existing schema. No code changes required.
    """
    with open(STUDIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_dashboards() -> list[dict[str, Any]]:
    """Return all dashboard catalogue entries. Reads data/dashboards.json.

    The "file" field points to an HTML export under /dashboard_files.
    If that file does not exist on disk, the UI shows a placeholder.
    """
    with open(DASHBOARDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_weeks() -> list[dict[str, Any]]:
    """Return all weekly reporting periods, oldest first. Reads
    data/weeks.json. To add a new week: append an entry with a unique
    "id", set "is_current" on it, and unset "is_current" on the old one.
    """
    with open(WEEKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def current_week_id() -> str:
    """Return the id of the week flagged "is_current", or the most
    recent week if none is flagged."""
    weeks = load_weeks()
    for w in weeks:
        if w.get("is_current"):
            return w["id"]
    return weeks[-1]["id"]


def get_week(week_id: str) -> dict[str, Any] | None:
    return next((w for w in load_weeks() if w["id"] == week_id), None)


@st.cache_data(show_spinner=False)
def _load_highlights_raw() -> list[dict[str, Any]]:
    with open(HIGHLIGHTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_highlights(week_id: str) -> dict[str, list[str]]:
    """Return {cohort: [bullets]} for the given week. Cohorts are one of
    DX_KSA, DX_JOR, PAX_KSA, PAX_JOR. A bullet starting with "Needs
    attention:" is flagged in the UI. Reads data/highlights.json.
    """
    result: dict[str, list[str]] = {}
    for h in _load_highlights_raw():
        if h["week_id"] == week_id:
            result[h["cohort"]] = h["bullets"]
    return result


@st.cache_data(show_spinner=False)
def _load_surveys_raw() -> list[dict[str, Any]]:
    with open(SURVEYS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_surveys(week_id: str) -> list[dict[str, Any]]:
    """Return surveys completed in the given week, with completion_pct
    and the linked dashboard's title attached. Reads data/surveys.json.
    """
    dashboards_by_id = {d["id"]: d for d in load_dashboards()}
    out = []
    for s in _load_surveys_raw():
        if s["week_id"] != week_id:
            continue
        sent = s["sent"]
        responses = s["responses"]
        dashboard = dashboards_by_id.get(s.get("dashboard_id"))
        out.append(
            {
                **s,
                "completion_pct": round((responses / sent) * 100, 1) if sent else 0,
                "dashboard_title": dashboard["title"] if dashboard else None,
            }
        )
    return out


@st.cache_data(show_spinner=False)
def _load_issues_raw() -> list[dict[str, Any]]:
    with open(ISSUES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_issues(week_id: str) -> list[dict[str, Any]]:
    """Return WhatsApp/technical issues manually logged for the given
    week, most recent first. Each item may carry a masked
    reference_type/reference_id ("driver" or "passenger" + an internal
    case code) - never a phone number or other personal identifier, per
    the privacy rules in README.md. Reads data/issues.json.
    """
    items = [i for i in _load_issues_raw() if i["week_id"] == week_id]
    return sorted(items, key=lambda i: i["logged_date"], reverse=True)


def issue_status_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in ISSUE_STATUSES}
    for i in issues:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return counts


@st.cache_data(show_spinner=False)
def _load_msu_dif_raw() -> dict[str, Any]:
    with open(MSU_DIF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_msu_dif_performance(week_id: str) -> dict[str, Any]:
    """Return {"meta": {"cities_live", "cities_total"}, "rows": [...]}
    for MSU (mystery shopper) and DIF (driver in-field) fieldwork in the
    given week. Reads data/msu_dif_performance.json.
    """
    raw = _load_msu_dif_raw()
    meta = raw["meta"].get(week_id, {"cities_live": 0, "cities_total": 0})
    rows = [r for r in raw["rows"] if r["week_id"] == week_id]
    return {"meta": meta, "rows": rows}


@st.cache_data(show_spinner=False)
def load_weekly_digest(week_id: str) -> dict[str, Any]:
    """Return the major-changes / recommended-next-steps digest for the
    given week (used by the Weekly Summary page). Reads
    data/weekly_digest.json.
    """
    with open(WEEKLY_DIGEST_PATH, "r", encoding="utf-8") as f:
        digests = json.load(f)
    return next(
        (d for d in digests if d["week_id"] == week_id),
        {"week_id": week_id, "is_sample_data": True, "major_changes": [], "recommended_areas": []},
    )


def dashboard_file_exists(dashboard: dict[str, Any]) -> bool:
    file_field = dashboard.get("file")
    if not file_field:
        return False
    return (BASE_DIR / file_field).exists()


def read_dashboard_html(dashboard: dict[str, Any]) -> str | None:
    if not dashboard_file_exists(dashboard):
        return None
    path = BASE_DIR / dashboard["file"]
    return path.read_text(encoding="utf-8")


def search_all(keyword: str) -> dict[str, list[dict[str, Any]]]:
    """Simple keyword search across studies and dashboards.

    Matches against title, description, topics, and key findings.
    Case-insensitive substring match -- good enough for the MVP;
    can be swapped for a proper search index later without changing
    callers.
    """
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return {"studies": [], "dashboards": []}

    matched_studies = []
    for s in load_studies():
        haystack = " ".join(
            [
                s.get("title", ""),
                s.get("description", ""),
                " ".join(s.get("topic", [])),
                " ".join(s.get("key_findings", [])),
                s.get("research_type", ""),
            ]
        ).lower()
        if keyword in haystack:
            matched_studies.append(s)

    matched_dashboards = []
    for d in load_dashboards():
        haystack = " ".join(
            [d.get("title", ""), d.get("description", ""), d.get("market", "")]
        ).lower()
        if keyword in haystack:
            matched_dashboards.append(d)

    return {"studies": matched_studies, "dashboards": matched_dashboards}


# --------------------------------------------------------------------------
# Future automation placeholders -- NOT wired up in the MVP.
# Implement these one at a time as each data source becomes available.
# --------------------------------------------------------------------------

def load_studies_from_snowflake(connection_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Placeholder for a future Snowflake-backed studies feed.

    Intended shape once implemented:
        1. Open a connection using `snowflake-connector-python` with
           credentials from st.secrets (never hard-coded).
        2. Query a STUDIES table/view that mirrors the studies.json
           schema used by load_studies().
        3. Return a list of dicts with the same keys so page code
           does not need to change.
    """
    raise NotImplementedError("Snowflake integration is not yet configured for Jeeny Insights Hub.")


def load_dashboard_metadata_from_powerbi(workspace_id: str | None = None) -> list[dict[str, Any]]:
    """Placeholder for pulling dashboard catalogue metadata (titles,
    last-refreshed timestamps, embed URLs) from the Power BI REST API.
    Would replace/augment data/dashboards.json.
    """
    raise NotImplementedError("Power BI integration is not yet configured for Jeeny Insights Hub.")


def load_responses_from_surveymonkey(survey_id: str | None = None) -> list[dict[str, Any]]:
    """Placeholder for pulling raw survey responses from the
    SurveyMonkey API to feed study sample sizes and key findings
    automatically instead of manual entry in studies.json.
    """
    raise NotImplementedError("SurveyMonkey integration is not yet configured for Jeeny Insights Hub.")


def load_studies_from_uploaded_csv(uploaded_file: Any) -> list[dict[str, Any]]:
    """Placeholder for letting a researcher upload a CSV of studies
    directly in the app (e.g. via st.file_uploader on an future Admin
    page) instead of editing studies.json by hand.
    """
    raise NotImplementedError("CSV upload ingestion is not yet implemented for Jeeny Insights Hub.")


def classify_text(texts: list[str]) -> list[str]:
    """Placeholder for automated topic/sentiment classification of
    open-text verbatims (e.g. app reviews, interview notes) using an
    LLM or classical NLP model. Would populate the "topic" field
    automatically instead of manual tagging.
    """
    raise NotImplementedError("Automated text classification is not yet implemented for Jeeny Insights Hub.")


def summarize_text(texts: list[str]) -> str:
    """Placeholder for automated summarization of raw verbatims into
    "key_findings" bullet points. Explicitly out of scope for the MVP
    per project requirements (no AI-generated answers yet).
    """
    raise NotImplementedError("Automated summarization is not yet implemented for Jeeny Insights Hub.")
