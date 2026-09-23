"""Google Sheets connector for the WhatsApp & technical issues panel -
lets whoever triages the ops WhatsApp groups keep logging issues in the
spreadsheet the team already uses, instead of a second manual entry into
data/issues.json.

Read-only, on purpose: this module never writes back to the sheet. It
uses the same Google Cloud service-account machinery as
modules/drive_client.py (google-auth + google-api-python-client, already
in requirements.txt - no new dependency), just against the Sheets API
instead of the Drive API, and a narrower `spreadsheets.readonly` scope.

The sheet is treated as a human-edited table with a header row - columns
can be in any order, and header text is matched loosely (case/space/
underscore-insensitive, a few synonyms per field - see _HEADER_ALIASES)
so this doesn't break the moment someone renames a column. Expected
fields, one row per issue:
    - a date column (e.g. "Date", "Logged", "Timestamp") - the day the
      issue was logged; the app derives which reporting week it falls
      into, so the sheet never needs to know the app's week_id format.
    - "Market" / "Country" - KSA/Saudi/Saudi Arabia -> KSA,
      JO/Jordan -> Jordan.
    - "Category" - free text (e.g. Tech, Feedback, Fraud signal).
    - "Status" - New / Under review / Reported out / Closed.
    - "Description" - what happened.
    - "Audience" / "Driver or Passenger" (optional) - driver/passenger.
    - "Reference ID" / "Case code" (optional) - a masked internal case
      code (e.g. DRV-KSA-88213), never a phone number - see README.md's
      Privacy section. Whoever maintains the sheet is responsible for
      not pasting raw phone numbers into it; this module does not scrub
      the sheet's free-text columns the way modules/snowflake_client.py
      does for feedback pulled from Snowflake.

Every function here returns (data, error) and never raises, matching
snowflake_client.py / surveymonkey_client.py / drive_client.py, so a bad
credential, an un-shared sheet, or a network failure degrades to the
offline data/issues.json snapshot instead of crashing the page.
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as _build_sheets_service

    GOOGLE_API_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when the optional deps aren't installed
    GOOGLE_API_AVAILABLE = False

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_DEFAULT_RANGE = "A:Z"

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "logged_date": ("date", "logged", "loggeddate", "timestamp", "datelogged"),
    "source": ("market", "country", "source"),
    "category": ("category", "type", "issuetype"),
    "status": ("status",),
    "description": ("description", "issue", "details", "summary", "notes"),
    "reference_type": ("audience", "referencetype", "driverorpassenger", "role"),
    "reference_id": ("referenceid", "caseid", "casecode", "id", "driverid", "passengerid"),
}

_MARKET_ALIASES = {
    "ksa": "KSA",
    "saudi": "KSA",
    "saudiarabia": "KSA",
    "sa": "KSA",
    "jo": "JO",
    "jordan": "JO",
}

_AUDIENCE_ALIASES = {
    "driver": "driver",
    "drivers": "driver",
    "dx": "driver",
    "passenger": "passenger",
    "passengers": "passenger",
    "pax": "passenger",
}

_STATUS_CANONICAL = {
    "new": "New",
    "underreview": "Under review",
    "reportedout": "Reported out",
    "closed": "Closed",
}


def _normalize_key(text: str) -> str:
    return "".join(ch for ch in text.strip().lower() if ch.isalnum())


def is_configured() -> bool:
    """True if service-account credentials + a spreadsheet id are
    available via st.secrets['google_sheets']. Safe to call outside a
    Streamlit runtime (returns False)."""
    if not GOOGLE_API_AVAILABLE:
        return False
    try:
        import streamlit as st

        section = st.secrets.get("google_sheets", {})
        has_creds = "service_account_json" in section or "service_account" in section
        return bool(has_creds and section.get("spreadsheet_id"))
    except Exception:  # noqa: BLE001
        return False


def _credentials_from_info(info: dict[str, Any]):
    return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)


def _get_credentials_from_secrets():
    try:
        import streamlit as st

        if "google_sheets" not in st.secrets:
            return None
        section = st.secrets["google_sheets"]
        if "service_account_json" in section:
            return _credentials_from_info(json.loads(section["service_account_json"]))
        if "service_account" in section:
            return _credentials_from_info(dict(section["service_account"]))
        return None
    except Exception:  # noqa: BLE001
        return None


def credentials_from_env() -> Any | None:
    """The standalone-script path: GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON
    holds the full service-account JSON key as a string (e.g. a GitHub
    Actions secret), matching drive_client.py's env-var convention."""
    raw = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    try:
        return _credentials_from_info(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return None


def _spreadsheet_id_from_secrets() -> str | None:
    try:
        import streamlit as st

        return st.secrets.get("google_sheets", {}).get("spreadsheet_id")
    except Exception:  # noqa: BLE001
        return None


def _worksheet_range_from_secrets() -> str:
    try:
        import streamlit as st

        return st.secrets.get("google_sheets", {}).get("worksheet_range") or _DEFAULT_RANGE
    except Exception:  # noqa: BLE001
        return _DEFAULT_RANGE


def spreadsheet_id_from_env() -> str | None:
    return os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID")


def _build_service(credentials: Any | None = None):
    if not GOOGLE_API_AVAILABLE:
        return None, "google-api-python-client / google-auth is not installed"
    creds = credentials if credentials is not None else _get_credentials_from_secrets()
    if creds is None:
        return None, "Google Sheets credentials not configured (st.secrets['google_sheets'] or GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON)"
    try:
        service = _build_sheets_service("sheets", "v4", credentials=creds, cache_discovery=False)
        return service, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def check_connection(spreadsheet_id: str, credentials: Any | None = None) -> tuple[bool, str | None]:
    """Cheap connectivity + access check: can this service account see the
    configured spreadsheet at all? A "not found" here almost always means
    the sheet hasn't been shared with the service account's email yet -
    see README.md for the exact one-time action."""
    service, error = _build_service(credentials)
    if service is None:
        return False, error
    try:
        service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="spreadsheetId").execute()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def _map_row(header_index: dict[str, int], row: list[str]) -> dict[str, str] | None:
    def cell(field: str) -> str | None:
        idx = header_index.get(field)
        if idx is None or idx >= len(row):
            return None
        value = row[idx].strip()
        return value or None

    description = cell("description")
    logged_date = cell("logged_date")
    if not description or not logged_date:
        return None  # not a usable issue row (e.g. a blank/section-header row)

    market_raw = cell("source")
    source = (_MARKET_ALIASES.get(_normalize_key(market_raw), market_raw) if market_raw else None) or "—"

    status_raw = cell("status")
    status = _STATUS_CANONICAL.get(_normalize_key(status_raw), status_raw) if status_raw else "New"

    audience_raw = cell("reference_type")
    reference_type = _AUDIENCE_ALIASES.get(_normalize_key(audience_raw)) if audience_raw else None

    return {
        "source": source,
        "category": cell("category") or "Feedback",
        "status": status,
        "description": description,
        "reference_type": reference_type,
        "reference_id": cell("reference_id"),
        "logged_date": logged_date[:10],
    }


def fetch_issues(
    spreadsheet_id: str | None = None,
    worksheet_range: str | None = None,
    credentials: Any | None = None,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Read every issue row from the configured sheet. Returns a list of
    dicts shaped like data/issues.json's rows (minus `id`/`week_id`,
    which the caller derives) or (None, error). A row missing a
    description or a date is silently skipped (treated as a blank/
    header/section row), everything else is returned even if some
    optional fields are missing.
    """
    service, error = _build_service(credentials)
    if service is None:
        return None, error

    sheet_id = spreadsheet_id or _spreadsheet_id_from_secrets() or spreadsheet_id_from_env()
    if not sheet_id:
        return None, "No spreadsheet_id configured (st.secrets['google_sheets']['spreadsheet_id'] or GOOGLE_SHEETS_SPREADSHEET_ID)"
    cell_range = worksheet_range or _worksheet_range_from_secrets()

    try:
        resp = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=cell_range, valueRenderOption="UNFORMATTED_VALUE")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"

    values = resp.get("values", [])
    if not values:
        return [], None

    header = [str(h) for h in values[0]]
    header_index: dict[str, int] = {}
    for col_idx, raw_header in enumerate(header):
        normalized = _normalize_key(raw_header)
        for field, aliases in _HEADER_ALIASES.items():
            if field in header_index:
                continue
            if normalized in aliases:
                header_index[field] = col_idx

    if "description" not in header_index or "logged_date" not in header_index:
        return None, "Sheet is missing a recognizable date and/or description column (see modules/sheets_client.py header aliases)"

    issues: list[dict[str, Any]] = []
    for row in values[1:]:
        str_row = [str(v) if v is not None else "" for v in row]
        mapped = _map_row(header_index, str_row)
        if mapped is not None:
            issues.append(mapped)
    return issues, None
