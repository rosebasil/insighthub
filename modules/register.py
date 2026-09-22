"""Research register + run manifests - the "no dashboards.json edit, ever"
publishing pipeline for recurring and ad hoc research workflows.

Two kinds of durable file live under version control (or wherever
DASHBOARD_FILES_DIR is mounted in production):

  data/research_register.json
      The workflow catalog - one row per recurring or ad hoc *topic*
      (e.g. "Driver NPS (KSA)", "No Rides After Sign-Up (Passengers)",
      an ad hoc study). See _REGISTER_REQUIRED_FIELDS for its schema.

  dashboard_files/runs/<workflow_id>/<run_id>.meta.json (+ output files)
      One manifest per completed *run* of a topic, sitting next to the
      files it describes. discover_runs() scans this tree on every call
      (cheap - it's a glob over local files) so a new run appears the
      next time any page loads, with zero code change and zero manual
      JSON edit. This is intentionally the same mechanism whether the
      files were written by a local script (scripts/run_*.py), copied
      down from Drive by scripts/sync_drive_runs.py, or saved by the
      "Add ad hoc study" form in the app itself - one discovery path,
      three producers.

Framework-agnostic on purpose (no `import streamlit`): standalone
scripts under /scripts import this module directly, outside any
Streamlit runtime. modules/data_loader.py wraps the read functions here
in @st.cache_data for the app's own use.

Validation is strict and silent-failure-proof: a run manifest missing a
required field, pointing at a file that doesn't exist, or reusing
another run's run_id is never shown as published - it comes back under
"needs_review" instead, the same "flag incomplete outputs for review"
guarantee data_loader.discover_generated_dashboards() already made for
plain dashboards.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DASHBOARD_FILES_DIR = BASE_DIR / "dashboard_files"
RUNS_DIR = DASHBOARD_FILES_DIR / "runs"
REGISTER_PATH = DATA_DIR / "research_register.json"

SOURCES = ["SurveyMonkey", "Snowflake", "Mixed", "Manual"]
CADENCES = ["weekly", "biweekly", "on-demand"]
WORKFLOW_STATUSES = ["active", "paused", "needs_setup"]
RUN_STATUSES = ["published", "failed", "needs_review"]
OUTPUT_FORMATS = ["dashboard_html", "pptx", "docx", "pdf", "link"]

_REGISTER_REQUIRED_FIELDS = ("id", "topic", "owner", "source", "cadence", "status")
_RUN_REQUIRED_FIELDS = (
    "run_id",
    "workflow_id",
    "topic",
    "source",
    "owner",
    "cadence",
    "period_start",
    "period_end",
    "data_as_of",
    "status",
)

_ID_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def slugify(text: str) -> str:
    """Lowercase, hyphenated slug for a workflow/run id fragment. Not
    guaranteed unique on its own - callers append a date or counter."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "item"


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------
# Workflow register (data/research_register.json)
# --------------------------------------------------------------------------


def load_register_raw() -> list[dict[str, Any]]:
    if not REGISTER_PATH.exists():
        return []
    with open(REGISTER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def register_by_id() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in load_register_raw()}


def validate_workflow(entry: dict[str, Any]) -> list[str]:
    """Return a list of validation error strings (empty = valid)."""
    errors = [f"missing required field '{f}'" for f in _REGISTER_REQUIRED_FIELDS if not entry.get(f)]
    if entry.get("source") and entry["source"] not in SOURCES:
        errors.append(f"source must be one of {SOURCES}, got {entry['source']!r}")
    if entry.get("cadence") and entry["cadence"] not in CADENCES:
        errors.append(f"cadence must be one of {CADENCES}, got {entry['cadence']!r}")
    if entry.get("status") and entry["status"] not in WORKFLOW_STATUSES:
        errors.append(f"status must be one of {WORKFLOW_STATUSES}, got {entry['status']!r}")
    if entry.get("id") and not _ID_SLUG.match(entry["id"]):
        errors.append("id must be a lowercase hyphenated slug")
    return errors


def upsert_workflow(entry: dict[str, Any]) -> tuple[bool, str | None]:
    """Add a new workflow to the register, or replace one with the same
    id (used both by the ad hoc study form and by any future admin UI).
    Never raises. Returns (ok, error)."""
    errors = validate_workflow(entry)
    if errors:
        return False, "; ".join(errors)
    rows = load_register_raw()
    rows = [r for r in rows if r["id"] != entry["id"]]
    rows.append(entry)
    try:
        _atomic_write_json(REGISTER_PATH, rows)
        return True, None
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# Run manifests (dashboard_files/runs/<workflow_id>/<run_id>.meta.json)
# --------------------------------------------------------------------------


def validate_run(manifest: dict[str, Any], meta_path: Path) -> list[str]:
    errors = [f"missing required field '{f}'" for f in _RUN_REQUIRED_FIELDS if not manifest.get(f)]
    if manifest.get("status") and manifest["status"] not in RUN_STATUSES:
        errors.append(f"status must be one of {RUN_STATUSES}, got {manifest['status']!r}")
    files = manifest.get("files")
    if not files or not isinstance(files, list):
        errors.append("'files' must be a non-empty list of {format, path} objects")
    else:
        for f in files:
            if not isinstance(f, dict) or not f.get("format") or not f.get("path"):
                errors.append(f"malformed file entry: {f!r}")
                continue
            if f["format"] not in OUTPUT_FORMATS:
                errors.append(f"file format must be one of {OUTPUT_FORMATS}, got {f['format']!r}")
            if f["format"] != "link":
                file_path = (meta_path.parent / f["path"]).resolve()
                if not str(file_path).startswith(str(RUNS_DIR.resolve())) or not file_path.exists():
                    errors.append(f"referenced file does not exist: {f['path']}")
    return errors


def discover_runs() -> dict[str, list[dict[str, Any]]]:
    """Scan dashboard_files/runs/**/*.meta.json. Returns {"published":
    [...], "needs_review": [{"file", "reason"}, ...]}. A run whose
    workflow_id has no matching row in the register still publishes (the
    register may lag a brand-new topic) but is flagged in the returned
    row via "workflow_known": False so the UI can show it distinctly.
    """
    published: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []

    if not RUNS_DIR.exists():
        return {"published": published, "needs_review": needs_review}

    known_workflow_ids = set(register_by_id().keys())
    seen_run_ids: dict[str, Path] = {}

    for meta_path in sorted(RUNS_DIR.glob("**/*.meta.json")):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            needs_review.append({"file": str(meta_path.relative_to(BASE_DIR)), "reason": f"Could not read/parse: {exc}"})
            continue

        errors = validate_run(manifest, meta_path)
        if errors:
            needs_review.append({"file": str(meta_path.relative_to(BASE_DIR)), "reason": "; ".join(errors)})
            continue

        run_id = manifest["run_id"]
        if run_id in seen_run_ids:
            needs_review.append(
                {
                    "file": str(meta_path.relative_to(BASE_DIR)),
                    "reason": f"Duplicate run_id '{run_id}' - also used by {seen_run_ids[run_id]}",
                }
            )
            continue
        seen_run_ids[run_id] = meta_path

        published.append(
            {
                **manifest,
                "workflow_known": manifest["workflow_id"] in known_workflow_ids,
                "meta_path": str(meta_path.relative_to(BASE_DIR)),
                "files": [
                    {**f, "abs_path": str((meta_path.parent / f["path"]).resolve())}
                    if f["format"] != "link"
                    else f
                    for f in manifest["files"]
                ],
            }
        )

    return {"published": published, "needs_review": needs_review}


def runs_for_workflow(workflow_id: str, runs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Published runs for one workflow, most recent period first. Pass a
    pre-fetched `runs` (discover_runs()["published"]) to avoid re-scanning
    disk when listing several workflows."""
    if runs is None:
        runs = discover_runs()["published"]
    rows = [r for r in runs if r["workflow_id"] == workflow_id]
    return sorted(rows, key=lambda r: (r.get("period_end") or "", r.get("generated_at") or ""), reverse=True)


def latest_run(workflow_id: str, runs: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    matches = runs_for_workflow(workflow_id, runs)
    published_only = [r for r in matches if r.get("status") == "published"]
    return published_only[0] if published_only else None


def save_run(
    workflow_id: str,
    run_id: str,
    manifest_fields: dict[str, Any],
    file_payloads: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    """Write a run's output file(s) and its manifest atomically. Files
    are written first, the meta.json last, so a crash mid-write can never
    leave a manifest pointing at files that don't exist - discover_runs()
    would otherwise have no way to tell a torn write from a valid run.

    file_payloads: [{"format": "dashboard_html", "filename": "...",
    "content": bytes}, ...] (bytes, not str - callers encode text as
    utf-8 first). A "link" format entry needs no "content"/"filename",
    just a "path" already set as a URL in manifest_fields (handled by the
    caller building `files` directly for that case).

    Returns (ok, error). Never raises.
    """
    run_dir = RUNS_DIR / workflow_id
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        written_files = []
        for payload in file_payloads:
            dest = run_dir / payload["filename"]
            fd, tmp_path = tempfile.mkstemp(dir=run_dir, prefix=f".{payload['filename']}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(payload["content"])
                os.replace(tmp_path, dest)
            except Exception:
                Path(tmp_path).unlink(missing_ok=True)
                raise
            written_files.append({"format": payload["format"], "path": payload["filename"]})

        extra_files = manifest_fields.get("extra_files", [])
        manifest = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            **{k: v for k, v in manifest_fields.items() if k != "extra_files"},
            "files": written_files + extra_files,
        }
        errors = validate_run(manifest, run_dir / f"{run_id}.meta.json")
        if errors:
            return False, "; ".join(errors)

        _atomic_write_json(run_dir / f"{run_id}.meta.json", manifest)
        return True, None
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def is_period_ready(period_end: date, window_days: int, as_of: date | None = None) -> bool:
    """True once `window_days` have fully elapsed since period_end - the
    generic form of the no-rides-after-signup readiness rule ("every
    signup in the period must have had its full N-day window elapse
    before the metric is trustworthy"). Reusable by any workflow with a
    similar lag-window shape."""
    as_of = as_of or date.today()
    return (as_of - period_end).days >= window_days


def next_expected_label(cadence: str, latest_period_end: str | None) -> str:
    """Human-readable "next period" caption for the Home page's
    recurring-workflow-status section, given the cadence and the latest
    known run's period_end (ISO date string, or None if it has never
    run). Deliberately doesn't claim a run is "overdue": cadence alone
    tells you when the next period *ends*, not when that workflow's own
    readiness_rule (e.g. no-rides-after-signup's extra 14-day eligibility
    lag on top of the cadence gap) actually clears - see each workflow's
    readiness_rule in the register/Studies Library for that.
    """
    if not latest_period_end:
        return "No runs yet"
    try:
        end = date.fromisoformat(latest_period_end)
    except ValueError:
        return "No runs yet"
    days = {"weekly": 7, "biweekly": 14, "on-demand": None}.get(cadence)
    if days is None:
        return "On demand"
    next_period_end = end + timedelta(days=days)
    return f"Next period ends {next_period_end.isoformat()}"
