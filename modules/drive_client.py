"""Google Drive connector for the run-publishing pipeline - the
"authenticated way for the deployed app to receive refreshed data" for
runs a Claude chat or Cowork task saves outside Snowflake/SurveyMonkey
(HTML dashboards, PPTX/DOCX/PDF reports, and their manifests).

IMPORTANT - this is NOT the same thing as the "Google Drive" connector
you can turn on inside a claude.ai chat. That connector lets a chat
*read/search/upload* Drive files during a conversation; it has no way to
reach this deployed Streamlit app, and this app has no way to reach it.
This module is a second, independent Drive connection - a Google Cloud
service account, authenticated with its own credentials (st.secrets or
an env var, never the chat's OAuth session) - that only *this app* (and
the standalone sync script) uses to read files back out of a shared
Drive folder. A chat's Drive connector and this module happen to point
at the same folder; they are otherwise unrelated. See README.md's
"Connecting real data sources" for the one-time setup this needs.

Convention: every workflow gets a subfolder under one shared root folder
(the Drive folder id configured below), named after its workflow_id
exactly as it appears in data/research_register.json - e.g.
"wf-no-rides-after-signup/". Inside that, a completed run is a
<run_id>.meta.json file plus whatever output file(s) it references, all
siblings in the same subfolder - the exact same layout
dashboard_files/runs/ uses locally, so sync_folder() below is just "walk
the Drive tree, mirror it onto disk at the same relative paths." Once
mirrored, modules/register.discover_runs() takes over - it doesn't care
whether a file arrived via Drive, a local script, or the ad hoc upload
form.

Every function here returns (data, error) and never raises, matching
snowflake_client.py and surveymonkey_client.py, so a bad credential, an
un-shared folder, or a network failure degrades the sync (skip this run,
try again next schedule) instead of crashing anything that calls it.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as _build_drive_service
    from googleapiclient.http import MediaIoBaseDownload

    GOOGLE_API_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when the optional deps aren't installed
    GOOGLE_API_AVAILABLE = False

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_FOLDER_MIME = "application/vnd.google-apps.folder"
# Native Google Docs/Slides/Sheets have no fixed byte content to download
# via get_media() (they need an export format instead) - a chat should
# upload/export an actual .pptx/.docx/.pdf/.html file, not leave a native
# Google file in the shared folder. Flagged, never silently skipped.
_NATIVE_GOOGLE_MIME_PREFIX = "application/vnd.google-apps."


def is_configured() -> bool:
    """True if service-account credentials are available via
    st.secrets['google_drive']. Safe to call outside a Streamlit
    runtime (returns False)."""
    if not GOOGLE_API_AVAILABLE:
        return False
    try:
        import streamlit as st

        return "google_drive" in st.secrets and "service_account_json" in st.secrets["google_drive"]
    except Exception:  # noqa: BLE001
        return False


def _credentials_from_info(info: dict[str, Any]):
    return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)


def _get_credentials_from_secrets():
    """The live app's path: st.secrets['google_drive']['service_account_json']
    (a JSON string) or ['service_account'] (an inline TOML table)."""
    try:
        import streamlit as st

        if "google_drive" not in st.secrets:
            return None
        section = st.secrets["google_drive"]
        if "service_account_json" in section:
            return _credentials_from_info(json.loads(section["service_account_json"]))
        if "service_account" in section:
            return _credentials_from_info(dict(section["service_account"]))
        return None
    except Exception:  # noqa: BLE001
        return None


def credentials_from_env() -> Any | None:
    """The standalone script's path: GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON
    holds the full service-account JSON key as a string (e.g. a GitHub
    Actions secret)."""
    raw = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    try:
        return _credentials_from_info(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return None


def folder_id_from_env() -> str | None:
    return os.environ.get("GOOGLE_DRIVE_FOLDER_ID")


def _folder_id_from_secrets() -> str | None:
    try:
        import streamlit as st

        return st.secrets.get("google_drive", {}).get("folder_id")
    except Exception:  # noqa: BLE001
        return None


def _build_service(credentials: Any | None = None):
    if not GOOGLE_API_AVAILABLE:
        return None, "google-api-python-client / google-auth is not installed"
    creds = credentials if credentials is not None else _get_credentials_from_secrets()
    if creds is None:
        return None, "Google Drive credentials not configured (st.secrets['google_drive'] or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON)"
    try:
        service = _build_drive_service("drive", "v3", credentials=creds, cache_discovery=False)
        return service, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def check_connection(folder_id: str, credentials: Any | None = None) -> tuple[bool, str | None]:
    """Cheap connectivity + access check: can this service account see the
    configured folder at all? A "File not found" here almost always means
    the folder hasn't been shared with the service account's email yet -
    see README.md for the exact one-time action."""
    service, error = _build_service(credentials)
    if service is None:
        return False, error
    try:
        service.files().get(fileId=folder_id, fields="id,name", supportsAllDrives=True).execute()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def _list_children(service, folder_id: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    items: list[dict[str, Any]] = []
    page_token = None
    try:
        while True:
            resp = (
                service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                    pageSize=200,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return items, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _walk_folder(service, folder_id: str, relative_prefix: str = "") -> tuple[list[dict[str, Any]] | None, str | None]:
    """Recursively list every file under folder_id, one level of
    subfolders deep is the documented convention (workflow_id
    subfolders) but this walks arbitrarily deep in case a producer
    nests further. Returns flat [{id, name, relative_path, mimeType,
    modifiedTime}] or (None, error)."""
    children, error = _list_children(service, folder_id)
    if children is None:
        return None, error

    out: list[dict[str, Any]] = []
    for item in children:
        rel_path = f"{relative_prefix}{item['name']}"
        if item["mimeType"] == _FOLDER_MIME:
            sub, sub_error = _walk_folder(service, item["id"], relative_prefix=f"{rel_path}/")
            if sub is None:
                return None, sub_error
            out.extend(sub)
        else:
            out.append({**item, "relative_path": rel_path})
    return out, None


def download_file(service, file_id: str, dest_path: Path) -> tuple[bool, str | None]:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    try:
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        tmp_path.write_bytes(buf.getvalue())
        os.replace(tmp_path, dest_path)
        return True, None
    except Exception as exc:  # noqa: BLE001
        Path(tmp_path).unlink(missing_ok=True)
        return False, f"{type(exc).__name__}: {exc}"


def sync_folder(folder_id: str, dest_root: Path, credentials: Any | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Mirror every file under the configured Drive folder into
    dest_root, preserving the workflow_id/run_id.ext relative layout.
    Returns ({"downloaded": [...], "skipped_native": [...], "errors":
    [...]}, error) - error is only set for a connection-level failure
    (can't list the folder at all); per-file problems land in the
    dict's "errors" list so one bad file doesn't abort the whole sync.
    """
    service, error = _build_service(credentials)
    if service is None:
        return None, error

    entries, error = _walk_folder(service, folder_id)
    if entries is None:
        return None, error

    downloaded: list[str] = []
    skipped_native: list[str] = []
    errors: list[str] = []

    for entry in entries:
        if entry["mimeType"].startswith(_NATIVE_GOOGLE_MIME_PREFIX):
            skipped_native.append(entry["relative_path"])
            continue
        dest_path = dest_root / entry["relative_path"]
        ok, dl_error = download_file(service, entry["id"], dest_path)
        if ok:
            downloaded.append(entry["relative_path"])
        else:
            errors.append(f"{entry['relative_path']}: {dl_error}")

    return {"downloaded": downloaded, "skipped_native": skipped_native, "errors": errors}, None
