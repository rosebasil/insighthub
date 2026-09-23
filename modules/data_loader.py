"""Data access layer for Jeeny Insights Hub.

Every page imports data through this module instead of reading files
directly. That means the *only* thing that needs to change when we move
from local JSON files to Snowflake, SurveyMonkey, or Power BI is the
implementation of the functions below -- page code stays the same.

Current state (MVP):
    Studies, dashboards, and the weekly summary are read from the JSON
    files in /data. This is the "sample data source" referenced in the
    project brief and is intentionally isolated behind get_* functions.

Live today:
    - In-app reviews & feedback (load_review_feedback) queries Snowflake
      directly via modules/snowflake_client.py when st.secrets['snowflake']
      is configured, falling back to data/sentiment_summary.json +
      data/sentiment_themes.json otherwise.
    - WhatsApp/technical issues (load_issues / load_open_issues) read
      directly, read-only, from the team's Google Sheet via
      modules/sheets_client.py when st.secrets['google_sheets'] is
      configured, falling back to data/issues.json otherwise - see
      issues_source_mode().

Planned automation (v2+) - not wired up yet, exist so the next engineer
can implement one function at a time without touching Streamlit page code:
    - load_studies_from_snowflake()
    - load_responses_from_surveymonkey()
    - load_dashboard_metadata_from_powerbi()
    - load_studies_from_uploaded_csv()
    - load_fieldwork_from_google_sheets()
    - classify_text() / summarize_text()  (NLP automation placeholders)
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DASHBOARD_FILES_DIR = BASE_DIR / "dashboard_files"
GENERATED_DASHBOARDS_DIR = DASHBOARD_FILES_DIR / "generated"

# Fields a generated dashboard's <id>.meta.json must have to be trusted
# and shown - see discover_generated_dashboards().
_GENERATED_DASHBOARD_REQUIRED_FIELDS = ("id", "title", "generated_at", "week_id")

STUDIES_PATH = DATA_DIR / "studies.json"
DASHBOARDS_PATH = DATA_DIR / "dashboards.json"
HIGHLIGHTS_PATH = DATA_DIR / "highlights.json"
SURVEYS_PATH = DATA_DIR / "surveys.json"
ISSUES_PATH = DATA_DIR / "issues.json"
MSU_DIF_PATH = DATA_DIR / "msu_dif_performance.json"
WEEKLY_DIGEST_PATH = DATA_DIR / "weekly_digest.json"
SENTIMENT_SUMMARY_PATH = DATA_DIR / "sentiment_summary.json"
SENTIMENT_THEMES_PATH = DATA_DIR / "sentiment_themes.json"
IN_APP_COMPLAINTS_PATH = DATA_DIR / "in_app_complaints.json"
FIELDWORK_PATH = DATA_DIR / "fieldwork.json"

ISSUE_STATUSES = ["New", "Under review", "Reported out", "Closed"]
OPEN_ISSUE_STATUSES = ["New", "Under review", "Reported out"]
COHORTS = ["DX_KSA", "DX_JOR", "PAX_KSA", "PAX_JOR"]
COHORT_LABELS = {
    "DX_KSA": "DX · KSA",
    "DX_JOR": "DX · Jordan",
    "PAX_KSA": "PAX · KSA",
    "PAX_JOR": "PAX · Jordan",
}
# Each cohort's (audience, market) pair, in the vocabulary the Home page
# filters use - "Driver"/"Passenger" and "KSA"/"Jordan" - so the market and
# audience selectors can filter cohort-tagged content generically instead
# of every call site re-deriving this mapping.
COHORT_AUDIENCE = {"DX_KSA": "Driver", "DX_JOR": "Driver", "PAX_KSA": "Passenger", "PAX_JOR": "Passenger"}
COHORT_MARKET = {"DX_KSA": "KSA", "DX_JOR": "Jordan", "PAX_KSA": "KSA", "PAX_JOR": "Jordan"}
MARKETS = ["All", "KSA", "Jordan"]
AUDIENCES = ["All", "Driver", "Passenger"]
THEME_TREND_WEEKS = 6

SNOWFLAKE_UNAVAILABLE_MESSAGE = "Live Snowflake feedback data is not reachable right now"


def cohort_matches(cohort: str, market: str, audience: str) -> bool:
    """True if a cohort (DX_KSA etc.) matches the selected market/audience
    filters, where "All" always matches."""
    if market != "All" and COHORT_MARKET.get(cohort) != market:
        return False
    if audience != "All" and COHORT_AUDIENCE.get(cohort) != audience:
        return False
    return True


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


def studies_matching_filters(studies: list[dict[str, Any]], market: str, audience: str) -> list[dict[str, Any]]:
    def _match(s: dict[str, Any]) -> bool:
        if audience != "All" and s.get("audience") != audience:
            return False
        if market != "All" and market not in (s.get("country") or []):
            return False
        return True

    return [s for s in studies if _match(s)]


def studies_completed_between(studies: list[dict[str, Any]], start_date: date, end_date: date) -> list[dict[str, Any]]:
    """Studies whose "date" (completion/publish date) falls within
    [start_date, end_date] inclusive."""
    start_iso, end_iso = start_date.isoformat(), end_date.isoformat()
    return [s for s in studies if start_iso <= s.get("date", "") <= end_iso]


@st.cache_data(show_spinner=False)
def load_dashboards() -> list[dict[str, Any]]:
    """Return all dashboard catalogue entries: the hand-curated ones in
    data/dashboards.json plus any auto-discovered generated dashboards
    that passed validation (see discover_generated_dashboards()) - this
    is how a new Claude-generated weekly dashboard shows up on its own,
    with no data/dashboards.json edit required.
    """
    with open(DASHBOARDS_PATH, "r", encoding="utf-8") as f:
        curated = json.load(f)
    generated = discover_generated_dashboards()
    return curated + generated["published"]


def dashboards_matching_filters(dashboards: list[dict[str, Any]], market: str, audience: str) -> list[dict[str, Any]]:
    def _match(d: dict[str, Any]) -> bool:
        if audience != "All" and d.get("audience") != audience:
            return False
        if market != "All" and market not in (d.get("market") or ""):
            return False
        return True

    return [d for d in dashboards if _match(d)]


def dashboards_updated_between(
    dashboards: list[dict[str, Any]], start_date: date, end_date: date
) -> list[dict[str, Any]]:
    """Dashboards whose "last_updated" falls within [start_date, end_date]
    inclusive. Dashboards missing last_updated never match (they can't be
    said to have updated in any particular week)."""
    start_iso, end_iso = start_date.isoformat(), end_date.isoformat()
    return [d for d in dashboards if d.get("last_updated") and start_iso <= d["last_updated"] <= end_iso]


WEEKS_PAST = 26   # ~6 months of history in the picker
WEEKS_FUTURE = 1  # let next week be selected a few days early if needed


def _most_recent_sunday(day: date) -> date:
    # date.weekday(): Monday=0 ... Sunday=6. Days since the most recent
    # Sunday (0 if `day` itself is a Sunday).
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _format_week_label(start: date) -> str:
    # Avoid "%-d" (no leading zero): it's a glibc/macOS-only strftime
    # extension and raises ValueError on Windows.
    return f"Week of {start.strftime('%b')} {start.day}"


def load_weeks(today: date | None = None) -> list[dict[str, Any]]:
    """Return Sunday-Saturday reporting weeks, oldest first, generated
    from the current date - not read from a file. `id` is the week's
    start date (YYYY-MM-DD), so it's stable and sortable without a
    separate numbering scheme. Covers the last WEEKS_PAST weeks through
    WEEKS_FUTURE weeks ahead; the current week is flagged "is_current".

    `today` is only for tests - real callers always use the current date.
    """
    today = today or date.today()
    current_sunday = _most_recent_sunday(today)
    weeks = []
    for i in range(-WEEKS_PAST, WEEKS_FUTURE + 1):
        start = current_sunday + timedelta(weeks=i)
        end = start + timedelta(days=6)
        weeks.append(
            {
                "id": start.isoformat(),
                "label": _format_week_label(start),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "is_current": i == 0,
            }
        )
    return weeks


def current_week_id(today: date | None = None) -> str:
    """Return the id of the current Sunday-Saturday week."""
    return _most_recent_sunday(today or date.today()).isoformat()


def get_week(week_id: str) -> dict[str, Any] | None:
    return next((w for w in load_weeks() if w["id"] == week_id), None)


def week_bounds(week_id: str) -> tuple[date, date] | None:
    """Return (start_date, end_date) as date objects for a week_id, or
    None if week_id isn't a valid ISO date."""
    try:
        start = date.fromisoformat(week_id)
    except (ValueError, TypeError):
        return None
    return start, start + timedelta(days=6)


def week_id_for_date(d: date) -> str:
    """Return the week_id (Sunday start date) whose Sun-Sat range contains `d`."""
    return _most_recent_sunday(d).isoformat()


def previous_week_id(week_id: str) -> str | None:
    bounds = week_bounds(week_id)
    if not bounds:
        return None
    return (bounds[0] - timedelta(days=7)).isoformat()


@st.cache_data(show_spinner=False)
def _load_highlights_raw() -> list[dict[str, Any]]:
    with open(HIGHLIGHTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_highlights(week_id: str) -> dict[str, dict[str, Any]]:
    """Return {cohort: {"bullets": [...], "dashboard_id": str|None,
    "study_id": str|None}} for the given week. Cohorts are one of
    DX_KSA, DX_JOR, PAX_KSA, PAX_JOR. A bullet starting with "Needs
    attention:" is flagged in the UI. "dashboard_id"/"study_id" (either
    or both may be set) back the "link to the supporting study or
    dashboard" the Home page shows per card. Reads data/highlights.json.
    """
    result: dict[str, dict[str, Any]] = {}
    for h in _load_highlights_raw():
        if h["week_id"] == week_id:
            result[h["cohort"]] = {
                "bullets": h["bullets"],
                "dashboard_id": h.get("dashboard_id"),
                "study_id": h.get("study_id"),
            }
    return result


@st.cache_data(show_spinner=False)
def _load_surveys_raw() -> list[dict[str, Any]]:
    with open(SURVEYS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_surveys(week_id: str, market: str = "All", audience: str = "All") -> list[dict[str, Any]]:
    """Return published surveys for the given week (never "draft" rows -
    those are SurveyMonkey-discovered surveys awaiting a human to assign
    a week_id/study before they're shown as real results), with
    completion_pct and the linked dashboard's title attached.

    A row's optional "market"/"audience" fields are matched against the
    market/audience filters when set on the row; a row that doesn't carry
    them always passes (untagged surveys aren't hidden by the filters).

    `sent` is optional - a row with sent=None (or missing) means the
    invitation count isn't verified, so completion_pct is None rather
    than guessed. Reads data/surveys.json.
    """
    dashboards_by_id = {d["id"]: d for d in load_dashboards()}
    out = []
    for s in _load_surveys_raw():
        if s.get("week_id") != week_id:
            continue
        if s.get("status") == "draft":
            continue
        if market != "All" and s.get("market") not in (None, market):
            continue
        if audience != "All" and s.get("audience") not in (None, audience):
            continue
        sent = s.get("sent")
        responses = s.get("responses")
        dashboard = dashboards_by_id.get(s.get("dashboard_id"))
        completion_pct = round((responses / sent) * 100, 1) if sent and responses is not None else None
        out.append(
            {
                **s,
                "completion_pct": completion_pct,
                "dashboard_title": dashboard["title"] if dashboard else None,
                "dashboard_link_id": dashboard["id"] if dashboard else None,
            }
        )
    return out


@st.cache_data(show_spinner=False)
def _load_issues_raw() -> list[dict[str, Any]]:
    with open(ISSUES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=900, show_spinner="Reading the issues sheet...")
def _fetch_issues_live_cached():
    """Cached for 15 minutes. Returns (rows, error) from
    sheets_client.fetch_issues() - rows are shaped like data/issues.json's
    entries minus `id`/`week_id`."""
    from . import sheets_client

    return sheets_client.fetch_issues()


def _issues_catalog() -> dict[str, Any]:
    """Every WhatsApp/technical issue across all weeks, each tagged with
    a derived week_id and a stable id. Tries a live, read-only pull from
    the team's Google Sheet (st.secrets['google_sheets']) first via
    modules/sheets_client.py, falling back to the data/issues.json
    snapshot otherwise. The sheet only needs a date column, not a
    week_id - each row's reporting week is derived with
    week_id_for_date(), so the sheet stays decoupled from the app's
    internal week id format. A row whose date can't be parsed is dropped.

    Returns {"mode": "live" | "snapshot" | "unavailable", "error": str |
    None, "issues": [...]}.
    """
    from . import sheets_client

    if sheets_client.is_configured():
        rows, error = _fetch_issues_live_cached()
        if error is not None:
            return {"mode": "unavailable", "error": error, "issues": []}
        issues: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            try:
                logged = date.fromisoformat(row["logged_date"])
            except (KeyError, ValueError):
                continue
            issues.append({**row, "id": f"sheet-{idx}", "week_id": week_id_for_date(logged)})
        issues.sort(key=lambda i: i["logged_date"], reverse=True)
        return {"mode": "live", "error": None, "issues": issues}

    return {"mode": "snapshot", "error": None, "issues": _load_issues_raw()}


def issues_source_mode() -> dict[str, Any]:
    """{"mode": "live" | "snapshot" | "unavailable", "error": str | None}
    describing where load_issues()/load_open_issues() data is currently
    coming from, for the Home page panel's source caption - cached, so
    calling this doesn't trigger an extra Sheets read."""
    catalog = _issues_catalog()
    return {"mode": catalog["mode"], "error": catalog["error"]}


_ISSUE_SOURCE_TO_MARKET = {"KSA": "KSA", "JO": "Jordan"}
_ISSUE_REF_TYPE_TO_AUDIENCE = {"driver": "Driver", "passenger": "Passenger"}


def _issue_matches_filters(issue: dict[str, Any], market: str, audience: str) -> bool:
    if market != "All" and _ISSUE_SOURCE_TO_MARKET.get(issue.get("source")) != market:
        return False
    if audience != "All":
        issue_audience = _ISSUE_REF_TYPE_TO_AUDIENCE.get(issue.get("reference_type"))
        if issue_audience is not None and issue_audience != audience:
            return False
    return True


def load_issues(week_id: str, market: str = "All", audience: str = "All") -> list[dict[str, Any]]:
    """Return WhatsApp/technical issues logged for the given week, most
    recent first. Live from the team's Google Sheet when
    st.secrets['google_sheets'] is configured (see
    modules/sheets_client.py), falling back to the data/issues.json
    snapshot otherwise - call issues_source_mode() to know which. Each
    item may carry a masked reference_type/reference_id ("driver" or
    "passenger" + an internal case code) - never a phone number or other
    personal identifier, per the privacy rules in README.md. An issue
    with no reference_type (a general/technical one, not tied to one
    person) always passes the audience filter.
    """
    items = [
        i
        for i in _issues_catalog()["issues"]
        if i["week_id"] == week_id and _issue_matches_filters(i, market, audience)
    ]
    return sorted(items, key=lambda i: i["logged_date"], reverse=True)


def load_open_issues(market: str = "All", audience: str = "All") -> list[dict[str, Any]]:
    """Return every currently-open (non-Closed) issue across all weeks -
    this is an all-time backlog count, not scoped to one reporting week,
    which is what the Home page's "Open critical issues" stat card shows
    (labeled explicitly as all-time, per spec - it does not reset with
    the week picker).
    """
    return [
        i
        for i in _issues_catalog()["issues"]
        if i.get("status") in OPEN_ISSUE_STATUSES and _issue_matches_filters(i, market, audience)
    ]


def issue_status_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in ISSUE_STATUSES}
    for i in issues:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return counts


@st.cache_data(show_spinner=False)
def _load_msu_dif_raw() -> dict[str, Any]:
    with open(MSU_DIF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_COUNTRY_CODE_TO_MARKET = {"KSA": "KSA", "JO": "Jordan"}


def load_msu_dif_performance(week_id: str, market: str = "All") -> dict[str, Any]:
    """Return {"meta": {"cities_live", "cities_total"}, "rows": [...]}
    for MSU (mystery shopper) and DIF (driver in-field) fieldwork in the
    given week. MSU/DIF sessions aren't tied to a driver/passenger
    audience, so there's no audience filter here - only market. Reads
    data/msu_dif_performance.json.
    """
    raw = _load_msu_dif_raw()
    meta = raw["meta"].get(week_id, {"cities_live": 0, "cities_total": 0})
    rows = [
        r
        for r in raw["rows"]
        if r["week_id"] == week_id and (market == "All" or _COUNTRY_CODE_TO_MARKET.get(r.get("country")) == market)
    ]
    return {"meta": meta, "rows": rows}


def load_msu_dif_performance_all(market: str = "All") -> list[dict[str, Any]]:
    """Return every MSU/DIF fieldwork row across all weeks (most recent
    week first), for the Fieldwork & Quality detail page's full history.
    """
    raw = _load_msu_dif_raw()
    rows = [r for r in raw["rows"] if market == "All" or _COUNTRY_CODE_TO_MARKET.get(r.get("country")) == market]
    return sorted(rows, key=lambda r: r["week_id"], reverse=True)


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
# In-app reviews & feedback
#
# Live source (preferred): Snowflake JEENY_PROD.GENERAL.FEEDBACKEVENTS via
# modules/snowflake_client.py - one unified event log covering driver and
# passenger ratings, in-app ratings, and categorized support-ticket
# feedback across KSA and Jordan. This is NOT app-store or social-media
# data - do not label it that way in the UI.
#
# Offline fallback: data/sentiment_summary.json + data/sentiment_themes.json,
# kept current by scripts/refresh_snowflake_data.py on a schedule (see
# README.md) for whenever the app itself has no direct Snowflake access
# (e.g. local dev without secrets configured). Two files, kept
# deliberately separate so item volume is never confused with theme
# volume: a single item can carry more than one theme, so SUM(mentions)
# for a week can legitimately exceed that week's item_count - never
# derive one from the other.
# --------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _load_sentiment_summary_raw() -> list[dict[str, Any]]:
    with open(SENTIMENT_SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def _load_sentiment_themes_raw() -> list[dict[str, Any]]:
    with open(SENTIMENT_THEMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=900, show_spinner="Querying Snowflake...")
def _fetch_snowflake_range_cached(range_start_iso: str, range_end_iso: str):
    """Cached for 15 minutes per (range_start, range_end) - shared across
    all four cohorts at a given week/weeks_back, since the underlying
    Snowflake fetch is cohort-agnostic (filtered to a cohort afterward in
    Python). Returns (summary_rows, theme_rows, error). Records the
    refresh outcome exactly once per real fetch (not once per cohort)
    because this function's cache makes repeat calls with the same range
    not re-execute the body.
    """
    from datetime import date as _date

    from . import refresh_state, snowflake_client

    range_start = _date.fromisoformat(range_start_iso)
    range_end = _date.fromisoformat(range_end_iso)

    summary_rows, error = snowflake_client.fetch_review_summary_range(range_start, range_end)
    if error is None:
        theme_rows, error = snowflake_client.fetch_theme_counts_range(range_start, range_end)
    else:
        theme_rows = None

    if error is not None:
        refresh_state.record_refresh("snowflake", "error", error)
        return None, None, error

    refresh_state.record_refresh(
        "snowflake", "ok", rows_written=len(summary_rows) + len(theme_rows)
    )
    return summary_rows, theme_rows, None


def load_review_feedback(week_id: str, cohort: str, weeks_back: int = THEME_TREND_WEEKS) -> dict[str, Any]:
    """The single entry point views/home.py uses for the in-app reviews &
    feedback panel. Tries live Snowflake first (if st.secrets['snowflake']
    is configured); falls back to the offline JSON files otherwise.
    Returns:
      {
        "mode": "live" | "offline" | "unavailable",
        "error": str | None,      # set only when mode == "unavailable"
        "summary": {...} | None,  # item_count, rating, rating_count,
                                   # positive/neutral/negative_count,
                                   # source, last_updated - matches the
                                   # data/sentiment_summary.json row shape
                                   # either way, live or offline
        "trend": [{"week_id","label","themes":{theme:mentions}}, ...],
      }
    "unavailable" means Snowflake is configured but the query failed
    (bad credentials, warehouse suspended, network error, etc.) - the
    caller should show that error, not silently show offline data instead
    (that would misrepresent a real outage as "nothing happened yet").
    "offline" is not the same as "fake" - data/sentiment_summary.json and
    data/sentiment_themes.json are meant to be kept current by
    scripts/refresh_snowflake_data.py, so "offline" data is real,
    scheduled-refresh data whenever that pipeline is running; the caller
    should trust `summary["source"]`/`summary["last_updated"]` (which
    describe where that row actually came from) rather than assume
    "offline" means "sample".
    """
    from . import snowflake_client

    weeks = load_weeks()
    ids_in_order = [w["id"] for w in weeks]
    if week_id not in ids_in_order:
        return {"mode": "offline", "error": None, "summary": None, "trend": []}
    idx = ids_in_order.index(week_id)
    start_idx = max(0, idx - weeks_back + 1)
    window = weeks[start_idx : idx + 1]

    if snowflake_client.is_configured():
        summary_rows, theme_rows, error = _fetch_snowflake_range_cached(window[0]["id"], window[-1]["id"])
        if error is not None:
            return {"mode": "unavailable", "error": error, "summary": None, "trend": []}

        audience = COHORT_AUDIENCE[cohort]
        market = COHORT_MARKET[cohort]

        trend = []
        for w in window:
            w_start = date.fromisoformat(w["id"])
            themes = {
                r["THEME"]: r["MENTIONS"]
                for r in theme_rows
                if r["WEEK_START"] == w_start and r["AUDIENCE"] == audience and r["MARKET"] == market
            }
            trend.append({"week_id": w["id"], "label": w["label"], "themes": themes})

        sel_start = date.fromisoformat(week_id)
        summary_row = next(
            (
                r
                for r in summary_rows
                if r["WEEK_START"] == sel_start and r["AUDIENCE"] == audience and r["MARKET"] == market
            ),
            None,
        )
        summary = None
        if summary_row is not None:
            avg_rating = summary_row.get("AVG_RATING")
            latest_event = summary_row.get("LATEST_EVENT_AT")
            summary = {
                "item_count": summary_row.get("THEMED_ITEMS") or 0,
                "rating": round(float(avg_rating), 2) if avg_rating is not None else None,
                "rating_count": summary_row.get("RATED_ITEMS") or 0,
                "positive_count": summary_row.get("POSITIVE_COUNT"),
                "neutral_count": summary_row.get("NEUTRAL_COUNT"),
                "negative_count": summary_row.get("NEGATIVE_COUNT"),
                "source": "Jeeny in-app ratings & categorized feedback (Snowflake, live)",
                "last_updated": latest_event.date().isoformat() if hasattr(latest_event, "date") else None,
            }
        return {"mode": "live", "error": None, "summary": summary, "trend": trend}

    # Offline fallback - the JSON files kept current by the scheduled script.
    summary = next(
        (
            row
            for row in _load_sentiment_summary_raw()
            if row.get("week_id") == week_id and row.get("cohort") == cohort
        ),
        None,
    )
    themes_raw = _load_sentiment_themes_raw()
    trend = []
    for w in window:
        themes: dict[str, int] = {}
        for row in themes_raw:
            if row.get("week_id") == w["id"] and row.get("cohort") == cohort:
                theme = row.get("theme")
                mentions = row.get("mentions")
                if theme is not None and isinstance(mentions, (int, float)):
                    themes[theme] = themes.get(theme, 0) + mentions
        trend.append({"week_id": w["id"], "label": w.get("label", w["id"]), "themes": themes})
    return {"mode": "offline", "error": None, "summary": summary, "trend": trend}


_COHORT_BY_AUDIENCE_MARKET = {(COHORT_AUDIENCE[c], COHORT_MARKET[c]): c for c in COHORTS}


@st.cache_data(show_spinner=False)
def _load_in_app_complaints_raw() -> list[dict[str, Any]]:
    if not IN_APP_COMPLAINTS_PATH.exists():
        return []
    with open(IN_APP_COMPLAINTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=900, show_spinner="Querying Snowflake...")
def _fetch_complaints_cached(range_start_iso: str, range_end_iso: str, per_cohort_limit: int):
    """Cached for 15 minutes per (range, limit). Returns (rows, error)."""
    from datetime import date as _date

    from . import snowflake_client

    range_start = _date.fromisoformat(range_start_iso)
    range_end = _date.fromisoformat(range_end_iso)
    return snowflake_client.fetch_recent_complaints(range_start, range_end, per_cohort_limit=per_cohort_limit)


def load_in_app_complaints(week_id: str, cohort: str, per_cohort_limit: int = 15) -> dict[str, Any]:
    """Real driver/passenger complaint text + user IDs for one cohort in
    one week - the row-level counterpart to load_review_feedback()'s
    aggregate summary/trend. Tries live Snowflake first (if
    st.secrets['snowflake'] is configured), falls back to
    data/in_app_complaints.json otherwise. Returns:
      {"mode": "live" | "offline" | "unavailable", "error": str | None,
       "complaints": [{"user_id","city","rating","comment_ar",
       "comment_en","timestamp"}, ...]}
    Complaint-shaped only (see modules/snowflake_client.py's
    _COMPLAINTS_RANGE_SQL comment for the exact filter) - not every
    comment, and phone numbers are already redacted by the time this
    returns, live or offline.
    """
    from . import snowflake_client

    bounds = week_bounds(week_id)
    if bounds is None:
        return {"mode": "offline", "error": None, "complaints": []}
    start, end = bounds

    if snowflake_client.is_configured():
        rows, error = _fetch_complaints_cached(start.isoformat(), end.isoformat(), per_cohort_limit)
        if error is not None:
            return {"mode": "unavailable", "error": error, "complaints": []}
        complaints = []
        for r in rows:
            row_cohort = _COHORT_BY_AUDIENCE_MARKET.get((r.get("AUDIENCE_RAW", "").capitalize(), r.get("MARKET")))
            if row_cohort != cohort:
                continue
            ts = r.get("TIMESTAMP")
            complaints.append(
                {
                    "user_id": r.get("USER_ID"),
                    "city": r.get("CITY"),
                    "rating": r.get("RATING_STARS"),
                    "comment_ar": r.get("RATINGS_COMMENTS"),
                    "comment_en": r.get("EN_TRANSLATION") or None,
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else ts,
                }
            )
        complaints.sort(key=lambda c: c["timestamp"] or "", reverse=True)
        return {"mode": "live", "error": None, "complaints": complaints}

    # Offline fallback - data/in_app_complaints.json, a real snapshot.
    all_rows = _load_in_app_complaints_raw()
    complaints = [
        {
            "user_id": row.get("user_id"),
            "city": row.get("city"),
            "rating": row.get("rating"),
            "comment_ar": row.get("comment_ar"),
            "comment_en": row.get("comment_en"),
            "timestamp": row.get("timestamp"),
        }
        for row in all_rows
        if row.get("week_id") == week_id and row.get("cohort") == cohort
    ]
    complaints.sort(key=lambda c: c["timestamp"] or "", reverse=True)
    return {"mode": "offline", "error": None, "complaints": complaints}


def top_themes_with_delta(trend: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    """From load_review_feedback()'s "trend" list, return the top `top_n`
    themes for the most recent week in the window, each as {"theme",
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


def load_fieldwork(week_id: str, market: str = "All", audience: str = "All") -> list[dict[str, Any]]:
    """Return fieldwork completed in the given week (data/fieldwork.json),
    most recently completed first. Rows missing "completion_date" sort
    last rather than crashing. A row's optional "audience" field is
    matched against the audience filter when set; rows without it always
    pass (market already has a required field on every row).
    """
    items = [
        f
        for f in _load_fieldwork_raw()
        if f.get("week_id") == week_id
        and (market == "All" or f.get("market") == market)
        and (audience == "All" or f.get("audience") in (None, audience))
    ]
    return sorted(items, key=lambda f: f.get("completion_date") or "", reverse=True)


def load_fieldwork_all(market: str = "All", audience: str = "All") -> list[dict[str, Any]]:
    """Return every fieldwork record across all weeks (most recently
    completed first), for the Fieldwork & Quality detail page's full
    history. Same market/audience filtering as load_fieldwork(), just not
    scoped to a single week.
    """
    items = [
        f
        for f in _load_fieldwork_raw()
        if (market == "All" or f.get("market") == market)
        and (audience == "All" or f.get("audience") in (None, audience))
    ]
    return sorted(items, key=lambda f: f.get("completion_date") or "", reverse=True)


def discover_generated_dashboards() -> dict[str, list[dict[str, Any]]]:
    """Scan dashboard_files/generated/ for Claude-generated (or any
    automation-generated) weekly dashboards and validate each before it's
    allowed to appear anywhere in the app. This - plus load_dashboards()
    including its "published" output - is the "hub discovers new and
    updated files by stable ID, validates required metadata, and displays
    outputs that pass validation; flags incomplete outputs for review"
    mechanism: durable storage is this folder in the git repo itself, and
    "new file appears" means "next page load picks it up", no
    data/dashboards.json edit required.

    Convention: each dashboard is two files sharing a basename -
    `<slug>.html` (the report itself) and `<slug>.meta.json` (its
    metadata). A meta.json missing any of
    _GENERATED_DASHBOARD_REQUIRED_FIELDS, or whose `id` collides with
    another generated dashboard's `id` (stable-ID discovery only works if
    IDs are actually stable and unique), is returned under "needs_review"
    instead of "published" - it never silently appears in the UI.

    Returns {"published": [...], "needs_review": [{"file":..., "reason":...}, ...]}.
    Each published entry has the same shape as a data/dashboards.json row
    (title, description, audience, market, last_updated, file, ...) plus
    `"source": "generated"` and whatever extra metadata the meta.json
    carried (e.g. "metrics", "study_id").
    """
    published: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []

    if not GENERATED_DASHBOARDS_DIR.exists():
        return {"published": published, "needs_review": needs_review}

    seen_ids: set[str] = set()
    for meta_path in sorted(GENERATED_DASHBOARDS_DIR.glob("*.meta.json")):
        slug = meta_path.name[: -len(".meta.json")]
        html_path = meta_path.with_name(f"{slug}.html")

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            needs_review.append({"file": meta_path.name, "reason": f"Could not read/parse meta.json: {exc}"})
            continue

        missing = [field for field in _GENERATED_DASHBOARD_REQUIRED_FIELDS if not meta.get(field)]
        if missing:
            needs_review.append({"file": meta_path.name, "reason": f"Missing required field(s): {', '.join(missing)}"})
            continue
        if not html_path.exists():
            needs_review.append({"file": meta_path.name, "reason": f"No matching report file: {html_path.name}"})
            continue
        if meta["id"] in seen_ids:
            needs_review.append({"file": meta_path.name, "reason": f"Duplicate id '{meta['id']}' - ids must be unique"})
            continue
        seen_ids.add(meta["id"])

        published.append(
            {
                **meta,
                "source": "generated",
                "title": meta["title"],
                "description": meta.get("description", ""),
                "audience": meta.get("audience", "Driver"),
                "market": meta.get("market", "KSA & Jordan"),
                "last_updated": meta.get("generated_at", "")[:10],
                "file": str(html_path.relative_to(BASE_DIR)),
                "is_sample_data": False,
            }
        )

    return {"published": published, "needs_review": needs_review}


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
