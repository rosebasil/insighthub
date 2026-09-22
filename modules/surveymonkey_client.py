"""SurveyMonkey connector - UNTESTED, blocked pending access.

Unlike modules/snowflake_client.py, this module could not be verified
against a real account: no SurveyMonkey MCP connector or API token was
available in the session that built this. The endpoints, auth scheme and
response shape below follow SurveyMonkey's documented v3 REST API, but
treat this as a well-informed draft, not a proven integration - actually
running it against a real account may need small fixes (an endpoint that
moved, a field renamed, a scope that needs adjusting) that only testing
against the real account will surface.

What this needs to go live - the one-time admin request:
    1. In the Jeeny SurveyMonkey account, create (or reuse) an OAuth app
       / access token with these scopes: `surveys_read`, `responses_read`.
    2. Hand the resulting access token to whoever manages this repo's
       secrets - it becomes SURVEYMONKEY_ACCESS_TOKEN (for the scheduled
       script) and st.secrets['surveymonkey']['access_token'] (for local
       dev), the same pattern as Snowflake - see README.md.
    3. Once that token exists, run scripts/refresh_surveymonkey_data.py
       by hand once and fix whatever the real API returns differently
       from what's assumed here - error messages from _request() below
       are deliberately verbose (status code + response body) to make
       that fast.

Design mirrors snowflake_client.py on purpose: every function returns
(data, error) and never raises, so a broken or unconfigured SurveyMonkey
connection degrades the app instead of crashing it.
"""

from __future__ import annotations

from typing import Any

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    REQUESTS_AVAILABLE = False

API_BASE = "https://api.surveymonkey.com/v3"


def is_configured() -> bool:
    if not REQUESTS_AVAILABLE:
        return False
    try:
        import streamlit as st

        return bool(st.secrets.get("surveymonkey", {}).get("access_token"))
    except Exception:  # noqa: BLE001
        return False


def _get_token() -> str | None:
    try:
        import streamlit as st

        return st.secrets.get("surveymonkey", {}).get("access_token")
    except Exception:  # noqa: BLE001
        return None


def _request(
    path: str, params: dict[str, Any] | None = None, access_token: str | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """GET `path` (relative to API_BASE). Returns (json_body, error).
    Never raises. `access_token` overrides st.secrets, for the standalone
    script's env-var path.
    """
    if not REQUESTS_AVAILABLE:
        return None, "the 'requests' package is not installed"
    token = access_token or _get_token()
    if not token:
        return None, "SurveyMonkey access token not configured"

    try:
        resp = requests.get(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=20,
        )
    except requests.RequestException as exc:
        return None, f"{type(exc).__name__}: {exc}"

    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code} from SurveyMonkey: {resp.text[:500]}"

    try:
        return resp.json(), None
    except ValueError as exc:
        return None, f"Could not parse SurveyMonkey response as JSON: {exc}"


def list_surveys(access_token: str | None = None) -> tuple[list[dict[str, Any]] | None, str | None]:
    """GET /surveys - paginated; follows `links.next` until exhausted.
    Returns (surveys, error), each survey as SurveyMonkey returns it
    (id, title, nickname, date_created, date_modified, response_count,
    ...). Response_count on this list endpoint is often an estimate -
    get_survey_details() below returns the authoritative count for one
    survey.
    """
    all_surveys: list[dict[str, Any]] = []
    path = "/surveys"
    params: dict[str, Any] | None = {"per_page": 100}
    for _ in range(50):  # hard cap - never loop forever on a pagination bug
        body, error = _request(path, params=params, access_token=access_token)
        if error is not None:
            return None, error
        all_surveys.extend(body.get("data", []))
        next_url = body.get("links", {}).get("next")
        if not next_url:
            break
        path = next_url.replace(API_BASE, "")
        params = None  # `next` already carries its own query string
    return all_surveys, None


def get_survey_details(survey_id: str, access_token: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """GET /surveys/{id}/details - title, date_created/modified, question
    structure, and response_count (authoritative for this survey)."""
    return _request(f"/surveys/{survey_id}/details", access_token=access_token)


def get_response_count(survey_id: str, access_token: str | None = None) -> tuple[int | None, str | None]:
    body, error = get_survey_details(survey_id, access_token=access_token)
    if error is not None:
        return None, error
    return body.get("response_count"), None
