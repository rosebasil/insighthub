"""Studies Library - searchable, filterable catalogue of research studies."""

from datetime import datetime

import streamlit as st

from modules import styles
from modules.data_loader import load_studies, load_dashboards

styles.page_title("Studies Library")
st.caption("Browse, filter, and open every research study")

studies = load_studies()
dashboards = {d["id"]: d for d in load_dashboards()}

with st.expander("🔎 Filters", expanded=True):
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        audience_filter = st.multiselect("Audience", options=["Driver", "Passenger"])
    with fcol2:
        country_filter = st.multiselect("Country", options=["KSA", "Jordan"])
    with fcol3:
        type_filter = st.multiselect(
            "Research type",
            options=["Survey", "Interview", "Reviews", "Funnel Analysis"],
        )

    all_topics = sorted({t for s in studies for t in s.get("topic", [])})
    fcol4, fcol5 = st.columns(2)
    with fcol4:
        topic_filter = st.multiselect("Topic", options=all_topics)
    with fcol5:
        keyword = st.text_input("Keyword", placeholder="e.g. payment, prices, NPS")

    all_dates = sorted(s["date"] for s in studies)
    if all_dates:
        min_d = datetime.strptime(all_dates[0], "%Y-%m-%d").date()
        max_d = datetime.strptime(all_dates[-1], "%Y-%m-%d").date()
        if min_d == max_d:
            date_range = (min_d, max_d)
            st.caption(f"All studies dated {min_d.isoformat()}")
        else:
            date_range = st.slider(
                "Date range", min_value=min_d, max_value=max_d, value=(min_d, max_d), format="YYYY-MM-DD"
            )
    else:
        date_range = None


def matches(study: dict) -> bool:
    if audience_filter and study["audience"] not in audience_filter:
        return False
    if country_filter and not set(country_filter) & set(study.get("country", [])):
        return False
    if type_filter and study["research_type"] not in type_filter:
        return False
    if topic_filter and not set(topic_filter) & set(study.get("topic", [])):
        return False
    if date_range:
        study_date = datetime.strptime(study["date"], "%Y-%m-%d").date()
        if not (date_range[0] <= study_date <= date_range[1]):
            return False
    if keyword:
        haystack = " ".join(
            [study["title"], study["description"], " ".join(study.get("key_findings", []))]
        ).lower()
        if keyword.lower() not in haystack:
            return False
    return True


filtered = [s for s in studies if matches(s)]
st.caption(f"{len(filtered)} of {len(studies)} studies")

if not filtered:
    st.info("No studies match the selected filters.")

for s in filtered:
    with st.container(border=True):
        head_l, head_r = st.columns([1, 12], vertical_alignment="center")
        with head_l:
            st.image(str(styles.AUDIENCE_ICON[s["audience"]]), width=30)
        with head_r:
            title_line = f"**{s['title']}**"
            if s.get("critical"):
                title_line += "  🔴"
            st.markdown(title_line)

        badges = styles.audience_badge_html(s["audience"])
        badges += f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.TEXT_MUTED};border:1px solid {styles.BORDER_COLOR};">{" / ".join(s["country"])}</span>'
        badges += f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.TEXT_MUTED};border:1px solid {styles.BORDER_COLOR};">{s["research_type"]}</span>'
        for t in s.get("topic", []):
            badges += f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.TEXT_MUTED};border:1px solid {styles.BORDER_COLOR};">{t}</span>'
        st.markdown(badges, unsafe_allow_html=True)

        st.caption(s["description"])
        meta = f"🗓️ {s['reporting_period']}"
        if s.get("sample_size"):
            meta += f"  ·  👥 {s['sample_size']:,}"
        st.caption(meta)
        if s.get("is_sample_data"):
            styles.sample_data_caption()

        with st.expander("Key findings"):
            for kf in s.get("key_findings", []):
                st.markdown(f"- {kf}")

        dash = dashboards.get(s.get("dashboard_id"))
        if s.get("report_url"):
            st.link_button("Open report", s["report_url"], icon=":material/open_in_new:")
        elif dash:
            st.page_link("views/dashboards.py", label="Open dashboard", icon=":material/bar_chart:")
        else:
            st.button("Not available", disabled=True, key=f"btn-{s['id']}")
