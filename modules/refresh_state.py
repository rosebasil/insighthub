"""Tracks when each external data source last refreshed successfully.

Both the live app (when it queries Snowflake directly, if credentials are
configured) and the standalone scheduled scripts under /scripts write here,
so the Home page header always shows the true last-successful-refresh time
regardless of which path produced the data on disk.

Read/write both go through data/refresh_meta.json. This file is *state*,
not source content, but it's committed to the repo (not gitignored) on
purpose: the scheduled GitHub Actions job is the primary writer, and the
app reads whatever the last commit says without needing its own storage.
A local `streamlit run` with live Snowflake secrets configured also updates
it, best-effort - if the filesystem turns out to be read-only (e.g. some
hosting platforms), that failure is swallowed rather than crashing the page.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REFRESH_META_PATH = Path(__file__).resolve().parent.parent / "data" / "refresh_meta.json"

SOURCES = ["snowflake", "surveymonkey", "dashboards"]


def _load() -> dict[str, Any]:
    if not REFRESH_META_PATH.exists():
        return {}
    try:
        with open(REFRESH_META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def record_refresh(source: str, status: str, message: str = "", rows_written: int | None = None) -> None:
    """Record a refresh attempt for `source` ("snowflake", "surveymonkey",
    or "dashboards"). `status` is "ok" or "error". Never raises - a
    failure to persist this is not worth crashing the page over.
    """
    try:
        state = _load()
        state[source] = {
            "status": status,
            "message": message,
            "rows_written": rows_written,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        REFRESH_META_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REFRESH_META_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError:
        pass


def get_refresh_state(source: str) -> dict[str, Any] | None:
    """Return {"status", "message", "rows_written", "checked_at"} for the
    given source, or None if it has never reported in."""
    return _load().get(source)


def latest_successful_refresh() -> str | None:
    """Return the most recent "checked_at" among sources that last
    reported status "ok", or None if none have ever succeeded."""
    state = _load()
    successes = [v["checked_at"] for v in state.values() if v.get("status") == "ok" and v.get("checked_at")]
    return max(successes) if successes else None
