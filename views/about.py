"""About - scope, privacy, and roadmap."""

import streamlit as st

from modules import styles

styles.page_title("About")

st.write(
    "Jeeny Insights Hub brings passenger, driver, and market research into one "
    "searchable place: studies, dashboards, in-app reviews & feedback, and a weekly summary."
)

st.divider()
st.markdown("#### Data sources")
st.markdown(
    "- **In-app reviews & feedback** — live from Snowflake "
    "(`JEENY_PROD.GENERAL.FEEDBACKEVENTS`), with a scheduled offline fallback. "
    "This is Jeeny's own in-app rating/feedback log, not app-store or social-media data.\n"
    "- **Surveys** — discovered and refreshed from SurveyMonkey on a schedule "
    "(currently blocked on a SurveyMonkey access token; see README).\n"
    "- **Dashboards** — curated files plus auto-discovered generated reports "
    "(dropped into `dashboard_files/generated/`, no manual catalogue edit needed).\n"
    "- **Studies, highlights, issues, fieldwork** — still maintained in `data/*.json` "
    "until each has its own automated source; see README's \"Adding your real content\"."
)

st.divider()
st.markdown("#### Privacy")
st.markdown(
    "- No phone numbers or personal identifiers shown\n"
    "- Snowflake queries are aggregate/count-only — no raw comment text or personal "
    "identifier is ever selected, stored, or displayed\n"
    "- Real credentials never live in this repo — see README's \"Connecting real data sources\"\n"
    "- Internal use only"
)

st.divider()
st.markdown("#### Not in scope (by design)")
st.markdown(
    "- Login / permissions\n"
    "- A live Power BI connection\n"
    "- AI-generated answers or a chatbot\n"
    "- Action-management system"
)

st.divider()
st.page_link("views/home.py", label="Back to Home", icon=":material/home:")
