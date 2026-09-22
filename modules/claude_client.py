"""Optional "Analyze with Claude" helper for the ad hoc study form.

Separate from every other *_client.py in this app: it doesn't pull data
in, it sends a short prompt to the Claude API and returns a short
synthesis for the person filling out the form to read - never persisted
automatically, never required. Manual entry works completely without
this (see views/studies.py - the form saves with or without it).

Credentials: st.secrets['anthropic']['api_key'] (never hard-coded, never
committed - see .streamlit/secrets.toml.example). If missing, or if the
`anthropic` package isn't installed, is_configured() returns False and
the caller shows a plain "not configured" message instead of the button.
"""

from __future__ import annotations

from typing import Any

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when the optional dep isn't installed
    ANTHROPIC_AVAILABLE = False

DEFAULT_MODEL = "claude-sonnet-5"


def is_configured() -> bool:
    if not ANTHROPIC_AVAILABLE:
        return False
    try:
        import streamlit as st

        return "anthropic" in st.secrets and bool(st.secrets["anthropic"].get("api_key"))
    except Exception:  # noqa: BLE001
        return False


def _get_client() -> Any | None:
    try:
        import streamlit as st

        if "anthropic" not in st.secrets:
            return None
        api_key = st.secrets["anthropic"].get("api_key")
        if not api_key:
            return None
        return anthropic.Anthropic(api_key=api_key)
    except Exception:  # noqa: BLE001
        return None


def analyze_ad_hoc_study(title: str, objective: str, findings: str) -> tuple[str | None, str | None]:
    """Return (analysis_text, error). Never raises - a bad key, rate
    limit, or network failure just means no analysis, not a crashed
    form. Model is fixed at DEFAULT_MODEL unless
    st.secrets['anthropic']['model'] overrides it."""
    if not ANTHROPIC_AVAILABLE:
        return None, "the 'anthropic' package is not installed"
    client = _get_client()
    if client is None:
        return None, "Anthropic API key not configured in st.secrets['anthropic']"

    try:
        import streamlit as st

        model = st.secrets["anthropic"].get("model", DEFAULT_MODEL)
    except Exception:  # noqa: BLE001
        model = DEFAULT_MODEL

    prompt = (
        f"You are helping a market intelligence analyst at Jeeny review an ad hoc research study "
        f"before it's published to an internal insights hub. Study title: {title!r}. "
        f"Objective: {objective or '(not provided)'}. Findings as entered: {findings or '(not provided)'}. "
        "In 3-5 sentences: (1) restate the core takeaway in one sentence, (2) flag anything that "
        "looks like it needs a follow-up question or missing context, (3) suggest one concrete next "
        "step. Be concise and concrete - no preamble, no restating these instructions."
    )
    try:
        response = client.messages.create(
            model=model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return text.strip(), None
    except Exception as exc:  # noqa: BLE001 - a bad key, rate limit, or network failure must degrade, not crash
        return None, f"{type(exc).__name__}: {exc}"
