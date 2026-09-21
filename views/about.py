"""About - scope, privacy, and roadmap."""

import streamlit as st

from modules import styles

styles.page_title("About")

st.write(
    "Jeeny Insights Hub brings passenger, driver, and market research into one "
    "searchable place: studies, dashboards, and a weekly summary. Version 1 (MVP)."
)

st.divider()
st.markdown("#### 🔒 Privacy")
st.markdown(
    "- No phone numbers or personal identifiers shown\n"
    "- All data stays inside the app — nothing sent externally\n"
    "- Internal use only"
)

st.divider()
st.markdown("#### 🚫 Not in v1 (by design)")
st.markdown(
    "- Login / permissions\n"
    "- Live Snowflake / SurveyMonkey connections\n"
    "- AI-generated answers or chatbot\n"
    "- Action-management system"
)

st.divider()
st.markdown("#### 🔌 Next: connecting real data")
st.write("All data flows through `modules/data_loader.py`. Implement one function to go live — page code stays the same:")
st.markdown(
    "- `load_studies_from_snowflake()` — Snowflake\n"
    "- `load_responses_from_surveymonkey()` — SurveyMonkey\n"
    "- `load_dashboard_metadata_from_powerbi()` — Power BI\n"
    "- `load_studies_from_uploaded_csv()` — CSV upload\n"
    "- `classify_text()` / `summarize_text()` — automated tagging & summaries"
)
