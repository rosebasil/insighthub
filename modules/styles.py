"""Shared visual styling and brand assets for Jeeny Insights Hub.

Centralizing CSS, color tokens, and small HTML-snippet helpers here keeps
every page visually consistent and makes it easy to re-theme the app
later without touching page logic.

Brand colors: pink `#EC008C` (passenger) and purple `#662D91` (driver)
were sampled directly from the real Jeeny logo files in /assets, plus
dark navy, lime green and cool gray from the wider Jeeny palette. This
app serves both driver (DX) and passenger (PAX) audiences internally, so
**purple leads** (sidebar, primary actions, DX content) and **pink is
used sparingly** to mark passenger-specific (PAX) content, matching the
Jeeny brand rule that pink and purple should not appear at equal weight
in one composition.
"""

from pathlib import Path
from typing import Any

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"

LOGO_PASSENGER = ASSETS_DIR / "logo-passenger.png"   # full pink Jeeny logo
LOGO_DRIVER = ASSETS_DIR / "logo-driver.png"          # full purple Jeeny logo
ICON_PASSENGER = ASSETS_DIR / "icon-passenger.png"    # pink glyph only
ICON_DRIVER = ASSETS_DIR / "icon-driver.png"          # purple glyph only

# --- Brand palette -----------------------------------------------------
JEENY_PINK = "#EC008C"
JEENY_PINK_DARK = "#B80070"
JEENY_PURPLE = "#662D91"
JEENY_PURPLE_DARK = "#4F2372"
JEENY_NAVY = "#1A1347"
JEENY_LIME = "#BFD730"
COOL_GRAY = "#A7A9AC"
BG_LIGHT_GREY = "#F5F6F8"
CARD_BG = "#FFFFFF"
TEXT_DARK = "#1B1B1F"
TEXT_MUTED = "#6B6F76"
BORDER_COLOR = "#E7E8EC"

AUDIENCE_ICON = {"Driver": ICON_DRIVER, "Passenger": ICON_PASSENGER}
AUDIENCE_HEX = {"Driver": JEENY_PURPLE, "Passenger": JEENY_PINK}
COHORT_GROUP_HEX = {"DX": JEENY_PURPLE, "PAX": JEENY_PINK}
COHORT_LABELS = {
    "DX_KSA": "DX · KSA",
    "DX_JOR": "DX · Jordan",
    "PAX_KSA": "PAX · KSA",
    "PAX_JOR": "PAX · Jordan",
}
RESEARCH_TYPE_ICON = {
    "Survey": ":material/checklist:",
    "Interview": ":material/mic:",
    "Reviews": ":material/star:",
    "Funnel Analysis": ":material/filter_alt:",
}
SEVERITY_ICON = {"critical": "🔴", "watch": "🟡", "positive": "🟢"}

STATUS_HEX = {
    "New": COOL_GRAY,
    "Under review": "#C79A1E",
    "Reported out": JEENY_PURPLE,
    "Closed": "#4C9A5B",
    "GOOD": "#4C9A5B",
    "REVIEW": "#C79A1E",
    "BELOW MIN": "#C0392B",
    "SCORING PENDING": COOL_GRAY,
}
ISSUE_STATUS_ORDER = ["New", "Under review", "Reported out", "Closed"]


def cohort_group(cohort: str) -> str:
    return "PAX" if cohort.startswith("PAX") else "DX"


def compact_html(html: str) -> str:
    """Collapse a multi-line, indented HTML template down to a single
    line of markup.

    Streamlit renders unsafe_allow_html markdown through a CommonMark
    parser: a line that is blank *or whitespace-only* ends an HTML
    block early, and indented lines that follow get re-parsed as a
    literal code block instead of markup. That silently breaks any
    template built as an indented triple-quoted f-string once more than
    one is concatenated (e.g. a list of cards). Always pass generated
    HTML through this before handing it to st.markdown(unsafe_allow_html=True).
    """
    return "".join(line.strip() for line in html.splitlines())


def inject_global_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Poppins', sans-serif;
        }}

        .stApp {{
            background-color: {BG_LIGHT_GREY};
        }}

        h1, h2, h3, h4, h5 {{
            color: {JEENY_NAVY};
        }}

        section[data-testid="stSidebar"] {{
            background-color: {CARD_BG};
            border-right: 1px solid {BORDER_COLOR};
            border-top: 4px solid {JEENY_PURPLE};
        }}

        [data-testid="stSidebarNav"] a,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
            border-radius: 8px;
            font-weight: 500;
            color: {TEXT_DARK} !important;
        }}

        [data-testid="stSidebarNav"] a:hover,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
            background-color: {BG_LIGHT_GREY} !important;
        }}

        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background-color: {JEENY_PURPLE} !important;
        }}

        [data-testid="stSidebarNav"] a[aria-current="page"] span {{
            color: #fff !important;
        }}

        div.stButton > button, .stLinkButton > a, .stPageLink > a {{
            background-color: {JEENY_PURPLE};
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
        }}

        div.stButton > button:hover, .stLinkButton > a:hover, .stPageLink > a:hover {{
            background-color: {JEENY_PURPLE_DARK};
            color: white;
        }}

        div.stButton > button:disabled {{
            background-color: {BORDER_COLOR};
            color: {TEXT_MUTED};
        }}

        [data-testid="stMetric"] {{
            background-color: {CARD_BG};
            border: 1px solid {BORDER_COLOR};
            border-top: 4px solid {JEENY_PURPLE};
            border-radius: 12px;
            padding: 14px 16px 10px 16px;
        }}

        /* --- Jeeny Insights Hub custom components (see styles.py) --- */

        .jih-badge {{
            display: inline-block;
            font-size: 10.5px;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            padding: 3px 9px;
            border-radius: 999px;
            margin: 0 4px 4px 0;
        }}

        .jih-stat-tile {{
            background: {CARD_BG};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 16px 18px;
            box-shadow: 0 1px 2px rgba(26, 19, 71, 0.06);
        }}

        .jih-stat-tile__label {{
            font-size: 12.5px;
            color: {TEXT_MUTED};
            font-weight: 500;
            margin-bottom: 6px;
        }}

        .jih-stat-tile__value {{
            font-size: 28px;
            font-weight: 700;
        }}

        .jih-highlight-card {{
            background: {CARD_BG};
            border: 1px solid {BORDER_COLOR};
            border-top: 4px solid {JEENY_PURPLE};
            border-radius: 12px;
            padding: 16px 18px;
            height: 100%;
        }}

        .jih-highlight-card[data-group="PAX"] {{
            border-top-color: {JEENY_PINK};
        }}

        .jih-highlight-card h4 {{
            font-size: 14.5px;
            color: {JEENY_NAVY};
            margin: 0 0 10px 0;
        }}

        .jih-highlight-card ul {{
            margin: 0;
            padding-left: 18px;
            font-size: 13px;
            line-height: 1.55;
            color: {TEXT_DARK};
        }}

        .jih-highlight-card li {{
            margin-bottom: 7px;
        }}

        .jih-highlight-card li.needs-attention {{
            font-weight: 600;
            color: {JEENY_NAVY};
        }}

        .jih-highlight-card li.needs-attention::marker {{
            color: {JEENY_PINK};
        }}

        .jih-issue-card {{
            background: {BG_LIGHT_GREY};
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 8px;
            border-left: 3px solid {COOL_GRAY};
        }}

        .jih-issue-card__meta {{
            font-size: 10.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            color: {TEXT_MUTED};
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
        }}

        .jih-issue-card__desc {{
            font-size: 13px;
            color: {TEXT_DARK};
            line-height: 1.4;
        }}

        .jih-issue-card__ref {{
            margin-top: 5px;
            font-size: 11px;
            font-weight: 600;
            color: {JEENY_PURPLE};
            font-family: 'SFMono-Regular', Consolas, monospace;
        }}

        .jih-status-bar {{
            display: flex;
            gap: 3px;
            height: 6px;
            border-radius: 4px;
            overflow: hidden;
            margin: 4px 0 10px;
        }}

        .jih-bar-track {{
            display: inline-block;
            width: 64px;
            height: 6px;
            background: {BORDER_COLOR};
            border-radius: 4px;
            overflow: hidden;
            vertical-align: middle;
            margin-right: 6px;
        }}

        .jih-bar-fill {{
            height: 100%;
            background: {JEENY_PURPLE};
        }}

        table.jih-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        table.jih-table th {{
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            color: {TEXT_MUTED};
            font-weight: 600;
            padding: 6px 8px;
            border-bottom: 2px solid {BORDER_COLOR};
        }}

        table.jih-table td {{
            padding: 9px 8px;
            border-bottom: 1px solid {BORDER_COLOR};
            vertical-align: middle;
        }}

        table.jih-table tr:last-child td {{
            border-bottom: none;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand_header(logo_path: Path = LOGO_DRIVER, width: int = 130) -> None:
    """Render the sidebar brand mark + internal-use label. Call once per page."""
    st.image(str(logo_path), width=width)
    st.caption("🔒 Internal use only · sample data until connected live")


def page_title(title: str, icon: str = "") -> None:
    st.markdown(f"## {icon + ' ' if icon else ''}{title}")


def audience_badge_html(audience: str) -> str:
    color = AUDIENCE_HEX.get(audience, COOL_GRAY)
    return (
        f'<span class="jih-badge" style="background:{color}1a;color:{color};'
        f'border:1px solid {color}40;">{audience}</span>'
    )


def cohort_badge_html(cohort: str) -> str:
    group = cohort_group(cohort)
    color = COHORT_GROUP_HEX[group]
    label = COHORT_LABELS.get(cohort, cohort)
    return (
        f'<span class="jih-badge" style="background:{color};color:#fff;">{group}</span>'
        f'<span style="font-weight:600;color:{JEENY_NAVY};">{label}</span>'
    )


def status_pill_html(text: str) -> str:
    color = STATUS_HEX.get(text, COOL_GRAY)
    return (
        f'<span class="jih-badge" style="background:{color};color:#fff;'
        f'letter-spacing:0.02em;">{text}</span>'
    )


def bar_html(fraction: float, width_px: int = 64) -> str:
    pct = max(0, min(100, round((fraction or 0) * 100)))
    return (
        f'<span class="jih-bar-track" style="width:{width_px}px;">'
        f'<span class="jih-bar-fill" style="width:{pct}%;"></span></span>'
    )


def audience_badge(audience: str) -> None:
    """Legacy Streamlit-native badge (kept for call sites that don't yet
    use audience_badge_html)."""
    color = "violet" if audience == "Driver" else "red"
    st.badge(audience, icon=":material/circle:", color=color)


def sample_data_caption() -> None:
    st.caption("🧪 Sample data — replace via `data/*.json`")


def issue_card_html(issue: dict[str, Any]) -> str:
    ref = ""
    if issue.get("reference_id"):
        who = "Passenger" if issue.get("reference_type") == "passenger" else "Driver"
        ref = f'<div class="jih-issue-card__ref">{who} ID: {issue["reference_id"]}</div>'
    color = STATUS_HEX.get(issue["status"], COOL_GRAY)
    return compact_html(f"""
    <div class="jih-issue-card" style="border-left-color:{color};">
      <div class="jih-issue-card__meta">
        <span>{issue['source']} &middot; {issue['category']}</span>
        <span style="color:{color};">{issue['status']}</span>
      </div>
      <div class="jih-issue-card__desc">{issue['description']}</div>
      {ref}
    </div>
    """)


def status_bar_html(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    if not total:
        return ""
    segs = "".join(
        f'<div style="flex:{counts[s]};background:{STATUS_HEX.get(s, COOL_GRAY)};height:100%;"></div>'
        for s in ISSUE_STATUS_ORDER
        if counts.get(s)
    )
    return f'<div class="jih-status-bar">{segs}</div>'


def stat_tile_html(label: str, value: Any, accent_hex: str = JEENY_PURPLE) -> str:
    return compact_html(f"""
    <div class="jih-stat-tile">
      <div class="jih-stat-tile__label">{label}</div>
      <div class="jih-stat-tile__value" style="color:{accent_hex};">{value}</div>
    </div>
    """)


def delta_badge_html(delta: int | float | None, is_new: bool = False) -> str:
    """Small up/down/new indicator for a week-over-week change, reusing
    the same green/gray/red semantics as the MSU/DIF status pills
    (GOOD/SCORING PENDING/BELOW MIN) rather than inventing new colors."""
    if is_new or delta is None:
        return f'<span style="color:{COOL_GRAY};font-size:12px;">new</span>'
    if delta > 0:
        return f'<span style="color:#4C9A5B;font-weight:600;font-size:12px;">&#9650; +{delta}</span>'
    if delta < 0:
        return f'<span style="color:#C0392B;font-weight:600;font-size:12px;">&#9660; {delta}</span>'
    return f'<span style="color:{COOL_GRAY};font-size:12px;">&#9679; 0</span>'


def sentiment_mix_html(positive: int, neutral: int, negative: int) -> str:
    """Three-segment horizontal bar for an optional positive/neutral/
    negative breakdown. Callers must only invoke this when all three
    counts are present - it does not guess a missing one."""
    total = positive + neutral + negative
    if not total:
        return ""
    segs = "".join(
        f'<div style="flex:{count};background:{color};height:100%;"></div>'
        for count, color in [(positive, "#4C9A5B"), (neutral, COOL_GRAY), (negative, "#C0392B")]
        if count
    )
    pct = lambda n: round((n / total) * 100)
    return compact_html(f"""
    <div>
      <div class="jih-status-bar" style="margin-bottom:4px;">{segs}</div>
      <div style="font-size:11px;color:{TEXT_MUTED};">
        <span style="color:#4C9A5B;">{pct(positive)}% positive</span> &nbsp;
        <span style="color:{COOL_GRAY};">{pct(neutral)}% neutral</span> &nbsp;
        <span style="color:#C0392B;">{pct(negative)}% negative</span>
      </div>
    </div>
    """)
