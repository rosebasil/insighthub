"""Weekly Summary - major changes and recommended next steps, by week."""

import streamlit as st

from modules import styles
from modules.data_loader import current_week_id, get_week, load_weekly_digest, load_weeks

weeks = load_weeks()
week_ids_desc = [w["id"] for w in reversed(weeks)]


def _week_label(week_id: str) -> str:
    w = get_week(week_id)
    return f"{w['label']} (current)" if w.get("is_current") else w["label"]


top_l, top_r = st.columns([3, 1.4], vertical_alignment="bottom")
with top_r:
    selected_week_id = st.selectbox(
        "Week",
        options=week_ids_desc,
        index=week_ids_desc.index(current_week_id()),
        format_func=_week_label,
        key="selected_week_id",
    )

week = get_week(selected_week_id)
with top_l:
    styles.page_title("Weekly Summary")
    st.caption(f"Week of {week['start_date']} · per-cohort highlights, surveys and issues live on Home")

digest = load_weekly_digest(selected_week_id)
if digest.get("is_sample_data"):
    styles.sample_data_caption()

st.divider()
st.markdown("#### ⚠️ Major changes")
if not digest["major_changes"]:
    st.caption("No major changes logged for this week.")
for change in digest["major_changes"]:
    severity = change.get("severity", "watch")
    icon = styles.SEVERITY_ICON.get(severity, "🟡")
    with st.container(border=True):
        st.markdown(f"{icon} **{change['title']}**")
        st.caption(change["detail"])

st.divider()
st.markdown("#### 🔎 Recommended next steps")
if not digest["recommended_areas"]:
    st.caption("No recommendations logged for this week.")
for item in digest["recommended_areas"]:
    st.markdown(f"- {item}")

st.divider()
st.page_link("views/home.py", label="See per-cohort highlights, surveys & issues for this week", icon=":material/home:")
