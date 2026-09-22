"""Live Snowflake connector for in-app reviews & feedback.

This queries a real, verified table: JEENY_PROD.GENERAL.FEEDBACKEVENTS
(role ROLE_MARKET_INTELLIGENCE has read access; columns and value
vocabularies were inspected via INFORMATION_SCHEMA and sample GROUP BYs
before any query below was written - see README.md's "Connecting real
data sources" section for the discovery notes). It is one unified event
log covering driver and passenger ratings, in-app ratings, and
categorized support-ticket feedback across KSA and Jordan; it is NOT
app-store or social-media data, so the Home page must not label it that
way.

One correctness note worth keeping visible: this Snowflake account's
DAYOFWEEK() is 1-indexed with Sunday=1 (verified against known dates,
not assumed from generic docs - a 0-indexed assumption silently produced
Saturday-anchored "weeks" here). The week-bucket expression below
(DAYOFWEEK(...) - 1) is what makes buckets land on Sunday, matching
Jeeny's Sunday-Saturday reporting week.

Only aggregate queries are ever run here - GROUP BY counts, averages, and
sentiment splits, bucketed by week server-side. No row-level feedback,
and no PII columns ever selected (the table also has USER_MOBILE_NUMBER
and USER_NAME - never select them here or anywhere else in this app).

Credentials come from st.secrets["snowflake"] (a local
.streamlit/secrets.toml, gitignored, or the hosting platform's secrets
manager - see .streamlit/secrets.toml.example) - never hard-coded, never
committed. If they aren't configured, every function here returns
(None, "<message>") rather than raising, so the app falls back to
data/sentiment_summary.json / data/sentiment_themes.json (kept current by
the scheduled refresh script; see scripts/refresh_snowflake_data.py)
instead of crashing the page.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

try:
    import snowflake.connector
    from snowflake.connector import DictCursor

    SNOWFLAKE_DRIVER_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when the optional dep isn't installed
    SNOWFLAKE_DRIVER_AVAILABLE = False

FEEDBACK_TABLE = "JEENY_PROD.GENERAL.FEEDBACKEVENTS"

# Real values observed in USER_TYPE / COUNTRY on FEEDBACKEVENTS as of the
# schema inspection this connector was built against. If Jeeny adds a new
# market or renames these, update the CASE mappings below to match - don't
# guess new values.
_AUDIENCE_CASE = "CASE WHEN USER_TYPE = 'driver' THEN 'Driver' WHEN USER_TYPE = 'passenger' THEN 'Passenger' END"
_MARKET_CASE = "CASE WHEN COUNTRY = 'Saudi Arabia' THEN 'KSA' WHEN COUNTRY = 'Jordan' THEN 'Jordan' END"
# Sunday-anchored week bucket - see the DAYOFWEEK note in the module
# docstring for why "- 1" (not "- 0") is required on this account.
_WEEK_BUCKET = "DATEADD(day, -(DAYOFWEEK(TIMESTAMP) - 1), TIMESTAMP::date)"

_SUMMARY_RANGE_SQL = f"""
    SELECT
        {_WEEK_BUCKET} AS WEEK_START,
        {_AUDIENCE_CASE} AS AUDIENCE,
        {_MARKET_CASE} AS MARKET,
        COUNT(CASE WHEN CATEGORY IS NOT NULL THEN 1 END) AS THEMED_ITEMS,
        COUNT(RATING_STARS) AS RATED_ITEMS,
        AVG(RATING_STARS) AS AVG_RATING,
        COUNT(CASE WHEN OVERALL_SENTIMENT = 'Positive' THEN 1 END) AS POSITIVE_COUNT,
        COUNT(CASE WHEN OVERALL_SENTIMENT = 'Neutral' THEN 1 END) AS NEUTRAL_COUNT,
        COUNT(CASE WHEN OVERALL_SENTIMENT = 'Negative' THEN 1 END) AS NEGATIVE_COUNT,
        MAX(TIMESTAMP) AS LATEST_EVENT_AT
    FROM {FEEDBACK_TABLE}
    WHERE TIMESTAMP >= %(range_start)s AND TIMESTAMP < %(range_end_exclusive)s
      AND USER_TYPE IN ('driver', 'passenger')
      AND COUNTRY IN ('Saudi Arabia', 'Jordan')
    GROUP BY 1, 2, 3
"""

_THEMES_RANGE_SQL = f"""
    SELECT
        {_WEEK_BUCKET} AS WEEK_START,
        {_AUDIENCE_CASE} AS AUDIENCE,
        {_MARKET_CASE} AS MARKET,
        CATEGORY AS THEME,
        COUNT(*) AS MENTIONS
    FROM {FEEDBACK_TABLE}
    WHERE TIMESTAMP >= %(range_start)s AND TIMESTAMP < %(range_end_exclusive)s
      AND USER_TYPE IN ('driver', 'passenger')
      AND COUNTRY IN ('Saudi Arabia', 'Jordan')
      AND CATEGORY IS NOT NULL
    GROUP BY 1, 2, 3, 4
"""

_CONNECTIVITY_SQL = "SELECT 1 AS OK"


def is_configured() -> bool:
    """True if Snowflake credentials are present in st.secrets. Safe to
    call even outside a Streamlit runtime (returns False)."""
    if not SNOWFLAKE_DRIVER_AVAILABLE:
        return False
    try:
        import streamlit as st

        return "snowflake" in st.secrets
    except Exception:  # noqa: BLE001 - st.secrets raises if no secrets file exists at all
        return False


def _get_credentials() -> dict[str, Any] | None:
    """Credentials for the live app, from st.secrets['snowflake']. The
    standalone refresh script does NOT use this - it builds its own
    credentials dict from environment variables and passes it explicitly
    to the fetch_* functions below (see scripts/refresh_snowflake_data.py),
    since it runs outside any Streamlit runtime.
    """
    try:
        import streamlit as st

        if "snowflake" not in st.secrets:
            return None
        return dict(st.secrets["snowflake"])
    except Exception:  # noqa: BLE001
        return None


def _run(
    sql: str, params: dict[str, Any], credentials: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Open a fresh connection, run one query, return (rows, error).
    Never raises - callers get a clean (None, "message") on any failure
    (bad credentials, network issue, role lacks access, warehouse
    suspended, etc.) so the UI can degrade gracefully instead of crashing.

    `credentials`, when given, is used as-is (the standalone script's
    path). When omitted, falls back to st.secrets['snowflake'] (the live
    app's path).
    """
    if not SNOWFLAKE_DRIVER_AVAILABLE:
        return None, "snowflake-connector-python is not installed"
    creds = credentials if credentials is not None else _get_credentials()
    if creds is None:
        return None, "Snowflake credentials not configured in st.secrets['snowflake']"

    conn = None
    try:
        conn = snowflake.connector.connect(**creds)
        with conn.cursor(DictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return rows, None
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure must degrade, not crash
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass


def check_connection(credentials: dict[str, Any] | None = None) -> tuple[bool, str | None]:
    """Cheap connectivity check for a "Snowflake: connected / error" status
    line, distinct from an actual data query."""
    rows, error = _run(_CONNECTIVITY_SQL, {}, credentials=credentials)
    return (error is None and rows is not None), error


def _range_bounds(range_start: date, range_end_inclusive: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(range_start, time.min)
    end_exclusive_dt = datetime.combine(range_end_inclusive + timedelta(days=1), time.min)
    return start_dt, end_exclusive_dt


def fetch_review_summary_range(
    range_start: date, range_end_inclusive: date, credentials: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Return (rows, error) for every Sunday-Saturday week bucket that
    overlaps [range_start, range_end_inclusive]. Each row: {WEEK_START
    (date), AUDIENCE, MARKET, THEMED_ITEMS, RATED_ITEMS, AVG_RATING,
    POSITIVE_COUNT, NEUTRAL_COUNT, NEGATIVE_COUNT, LATEST_EVENT_AT} -
    never row-level feedback.
    """
    start_dt, end_exclusive_dt = _range_bounds(range_start, range_end_inclusive)
    return _run(
        _SUMMARY_RANGE_SQL,
        {"range_start": start_dt, "range_end_exclusive": end_exclusive_dt},
        credentials=credentials,
    )


def fetch_theme_counts_range(
    range_start: date, range_end_inclusive: date, credentials: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Return (rows, error). Each row: {WEEK_START (date), AUDIENCE,
    MARKET, THEME, MENTIONS}."""
    start_dt, end_exclusive_dt = _range_bounds(range_start, range_end_inclusive)
    return _run(
        _THEMES_RANGE_SQL,
        {"range_start": start_dt, "range_end_exclusive": end_exclusive_dt},
        credentials=credentials,
    )


# --------------------------------------------------------------------------
# No rides after sign-up (passengers)
#
# Business definition, confirmed with the hub's owner on 2026-09-22 (not
# invented - see PASSENGERS.VPASSENGERSPROFILE's real columns, verified
# via INFORMATION_SCHEMA before this was written):
#   - Audience: passengers only.
#   - Signup event: SIGNUPDATE.
#   - First-ride definition: FIRSTRIDE (a completed ride) - NOT
#     FIRSTREQUEST, which is only a ride request and may never convert.
#   - Window: NO_RIDES_WINDOW_DAYS (14) days after SIGNUPDATE.
#   - "No ride" = FIRSTRIDE IS NULL. A passenger only belongs in a
#     reporting period once their full window has elapsed (see
#     modules/register.is_period_ready()) - counting them earlier would
#     understate the no-ride rate for anyone who just hasn't had time to
#     ride yet.
#   - Eligibility: PHONECOUNTRYCODE IN ('SA', 'JO') (the app's two
#     markets), ISTEST excluded. This is a data-hygiene filter, not a
#     business-metric choice, so it wasn't part of the question asked.
# Aggregate-only, like the feedback queries above - no PASSENGERID is
# ever selected.
# --------------------------------------------------------------------------

NO_RIDES_TABLE = "JEENY_PROD.PASSENGERS.VPASSENGERSPROFILE"
NO_RIDES_WINDOW_DAYS = 14

_NO_RIDES_MARKET_CASE = "CASE WHEN PHONECOUNTRYCODE = 'SA' THEN 'KSA' WHEN PHONECOUNTRYCODE = 'JO' THEN 'Jordan' END"

_NO_RIDES_SQL = f"""
    SELECT
        {_NO_RIDES_MARKET_CASE} AS MARKET,
        COUNT(*) AS SIGNUPS,
        COUNT(CASE WHEN FIRSTRIDE IS NULL THEN 1 END) AS NO_RIDE_COUNT,
        COUNT(CASE WHEN FIRSTRIDE IS NOT NULL AND DATEDIFF(day, SIGNUPDATE, FIRSTRIDE) <= %(window_days)s THEN 1 END) AS RODE_WITHIN_WINDOW_COUNT
    FROM {NO_RIDES_TABLE}
    WHERE SIGNUPDATE >= %(period_start)s AND SIGNUPDATE < %(period_end_exclusive)s
      AND PHONECOUNTRYCODE IN ('SA', 'JO')
      AND (ISTEST IS NULL OR ISTEST = FALSE)
    GROUP BY 1
"""


def fetch_no_rides_after_signup(
    period_start: date,
    period_end_inclusive: date,
    window_days: int = NO_RIDES_WINDOW_DAYS,
    credentials: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Return (rows, error) for passengers who signed up in [period_start,
    period_end_inclusive]. Each row: {MARKET, SIGNUPS, NO_RIDE_COUNT,
    RODE_WITHIN_WINDOW_COUNT}. Callers should only treat a period as
    reportable once modules/register.is_period_ready(period_end_inclusive,
    window_days) is True - this function itself doesn't enforce that, so
    it can also be used to preview an in-progress period.
    """
    start_dt, end_exclusive_dt = _range_bounds(period_start, period_end_inclusive)
    return _run(
        _NO_RIDES_SQL,
        {"period_start": start_dt, "period_end_exclusive": end_exclusive_dt, "window_days": window_days},
        credentials=credentials,
    )
