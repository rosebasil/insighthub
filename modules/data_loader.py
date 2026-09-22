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
    - load_sentiment_from_snowflake()
    - load_fieldwork_from_google_sheets()
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
SENTIMENT_SUMMARY_PATH = DATA_DIR / "sentiment_summary.json"
SENTIMENT_THEMES_PATH = DATA_DIR / "sentiment_themes.json"
FIELDWORK_PATH = DATA_DIR / "fieldwork.json"

ISSUE_STATUSES = ["New", "Under review", "Reported out", "Closed"]
COHORTS = ["DX_KSA", "DX_JOR", "PAX_KSA", "PAX_JOR"]
COHORT_LABELS = {
    "DX_KSA": "DX · KSA",
    "DX_JOR": "DX · Jordan",
    "PAX_KSA": "PAX · KSA",
    "PAX_JOR": "PAX · Jordan",
}
SOURCE_TYPES = ["social_media", "app_reviews"]
SOURCE_TYPE_LABELS = {"social_media": "Social Media", "app_reviews": "App Reviews"}
THEME_TREND_WEEKS = 6


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


# --------------------------------------------------------------------------
# Social sentiment & app reviews
#
# Two files, kept deliberately separate so item volume is never confused
# with theme volume:
#   - sentiment_summary.json: one row per (week, cohort, source_type) with
#     the week's item_count (reviews/posts actually collected) plus
#     whatever optional aggregate fields are available (rating, sentiment
#     mix). This is the "how much did we look at, and what's the headline
#     number" row.
#   - sentiment_themes.json: one row per (week, cohort, source_type,
#     theme) with that theme's mention count. A single review/post can be
#     tagged with more than one theme, so SUM(mentions) for a week can
#     legitimately exceed that week's item_count in sentiment_summary -
#     never derive one from the other.
# Both are empty lists until real data is added; see README.md for the
# exact field-by-field format.
# --------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _load_sentiment_summary_raw() -> list[dict[str, Any]]:
    with open(SENTIMENT_SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sentiment_summary(week_id: str, cohort: str, source_type: str) -> dict[str, Any] | None:
    """Return the one summary row for this (week, cohort, source_type),
    or None if nothing has been recorded for it yet."""
    for row in _load_sentiment_summary_raw():
        if row.get("week_id") == week_id and row.get("cohort") == cohort and row.get("source_type") == source_type:
            return row
    return None


@st.cache_data(show_spinner=False)
def _load_sentiment_themes_raw() -> list[dict[str, Any]]:
    with open(SENTIMENT_THEMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_theme_trend(
    week_id: str, cohort: str, source_type: str, weeks_back: int = THEME_TREND_WEEKS
) -> list[dict[str, Any]]:
    """Return up to `weeks_back` weeks of theme-mention data ending at
    week_id (oldest first), as [{"week_id", "label", "themes": {theme:
    mentions}}, ...]. Returns fewer entries if fewer weeks exist in
    weeks.json - never pads or invents data. Returns [] if week_id isn't
    a known week.
    """
    weeks = load_weeks()
    ids_in_order = [w["id"] for w in weeks]
    if week_id not in ids_in_order:
        return []
    idx = ids_in_order.index(week_id)
    start_idx = max(0, idx - weeks_back + 1)
    window = weeks[start_idx : idx + 1]

    raw = _load_sentiment_themes_raw()
    trend = []
    for w in window:
        themes: dict[str, int] = {}
        for row in raw:
            if row.get("week_id") == w["id"] and row.get("cohort") == cohort and row.get("source_type") == source_type:
                theme = row.get("theme")
                mentions = row.get("mentions")
                if theme is not None and isinstance(mentions, (int, float)):
                    themes[theme] = themes.get(theme, 0) + mentions
        trend.append({"week_id": w["id"], "label": w.get("label", w["id"]), "themes": themes})
    return trend


def top_themes_with_delta(trend: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    """From load_theme_trend()'s output, return the top `top_n` themes for
    the most recent week in the trend window, each as {"theme",
    "mentions", "delta", "is_new"}. `delta` is the change vs. the
    previous week in the window (None if that theme has no prior-week
    count to compare against - e.g. only one week of history exists, or
    the theme wasn't tracked last week). Never invents a delta.
    """
    if not trend:
        return []
    current = trend[-1]["themes"]
    previous = trend[-2]["themes"] if len(trend) >= 2 else {}
    items = []
    for theme, mentions in current.items():
        prev_mentions = previous.get(theme)
        delta = (mentions - prev_mentions) if prev_mentions is not None else None
        items.append({"theme": theme, "mentions": mentions, "delta": delta, "is_new": prev_mentions is None})
    items.sort(key=lambda x: x["mentions"], reverse=True)
    return items[:top_n]


# --------------------------------------------------------------------------
# Fieldwork completed
# --------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _load_fieldwork_raw() -> list[dict[str, Any]]:
    with open(FIELDWORK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_fieldwork(week_id: str) -> list[dict[str, Any]]:
    """Return fieldwork completed in the given week (data/fieldwork.json),
    most recently completed first. Rows missing "completion_date" sort
    last rather than crashing.
    """
    items = [f for f in _load_fieldwork_raw() if f.get("week_id") == week_id]
    return sorted(items, key=lambda f: f.get("completion_date") or "", reverse=True)


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


def load_sentiment_from_snowflake(week_id: str, connection_config: dict[str, Any] | None = None) -> tuple[list, list]:
    """Placeholder for a future Snowflake-backed sentiment feed (social
    listening + app store review exports, e.g. via Talkwalker/Brandwatch/
    App Store Connect/Play Console pipelines landed in Snowflake).

    Intended shape once implemented:
        1. Open a connection using `snowflake-connector-python` with
           credentials from st.secrets (never hard-coded).
        2. Query two views for the given week - one that mirrors the
           per-(week, cohort, source_type) row shape used by
           load_sentiment_summary(), one that mirrors the per-(week,
           cohort, source_type, theme) row shape used by
           load_theme_trend() - and return (summary_rows, theme_rows).
        3. Replace the bodies of _load_sentiment_summary_raw() and
           _load_sentiment_themes_raw() with these queries (cached per
           week_id instead of read-once-and-filter, since a warehouse
           query is more expensive than reading a small JSON file).
    """
    raise NotImplementedError("Snowflake sentiment integration is not yet configured for Jeeny Insights Hub.")


def load_fieldwork_from_google_sheets(sheet_id: str | None = None) -> list[dict[str, Any]]:
    """Placeholder for reading the team's shared fieldwork tracker
    straight from Google Sheets instead of data/fieldwork.json, so
    whoever runs a study logs completion once in the sheet everyone
    already uses.

    Intended shape once implemented:
        1. Use `gspread` (or the Sheets API directly) with a service
           account credential from st.secrets.
        2. Read the tracker sheet and map its columns onto the row shape
           documented in README.md for data/fieldwork.json (study,
           objective, market, week_id, completion_date, report_url).
        3. Replace the body of _load_fieldwork_raw() with this read,
           cached with a short TTL (e.g. @st.cache_data(ttl=300)) so
           the team sees updates within a few minutes without hammering
           the Sheets API on every page load.
    """
    raise NotImplementedError("Google Sheets fieldwork integration is not yet configured for Jeeny Insights Hub.")


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
