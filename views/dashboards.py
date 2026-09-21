"""Dashboards - catalogue of available dashboards with inline viewing."""

import streamlit as st
import streamlit.components.v1 as components

from modules import styles
from modules.data_loader import load_dashboards, dashboard_file_exists, read_dashboard_html

styles.page_title("Dashboards")
st.caption("Open a live dashboard or preview a bundled HTML export")

dashboards = load_dashboards()

if "open_dashboard" not in st.session_state:
    st.session_state.open_dashboard = None

cols = st.columns(2)
for i, d in enumerate(dashboards):
    col = cols[i % 2]
    with col:
        with st.container(border=True):
            head_l, head_r = st.columns([1, 12], vertical_alignment="center")
            with head_l:
                st.image(str(styles.AUDIENCE_ICON[d["audience"]]), width=28)
            with head_r:
                st.markdown(f"**{d['title']}**")

            exists = dashboard_file_exists(d)
            badges = styles.audience_badge_html(d["audience"])
            badges += f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.TEXT_MUTED};border:1px solid {styles.BORDER_COLOR};">{d["market"]}</span>'
            st.markdown(badges, unsafe_allow_html=True)

            st.caption(d["description"])
            st.caption(f"🗓️ Updated {d['last_updated']}")
            if exists:
                st.badge("File available", icon=":material/check_circle:", color="green")
            else:
                st.badge("Placeholder — no file yet", icon=":material/upload_file:", color="orange")
            if d.get("is_sample_data"):
                styles.sample_data_caption()

            if st.button("Open dashboard", key=f"open-{d['id']}", icon=":material/open_in_full:"):
                st.session_state.open_dashboard = d["id"]

st.divider()

if st.session_state.open_dashboard:
    active = next((d for d in dashboards if d["id"] == st.session_state.open_dashboard), None)
    if active:
        st.markdown(f"### {active['title']}")
        if dashboard_file_exists(active):
            html = read_dashboard_html(active)
            components.html(html, height=560, scrolling=True)
        else:
            st.warning(
                f"**No dashboard file found yet for \"{active['title']}\".**\n\n"
                f"Place the real HTML export at:\n\n`{active['file']}`\n\n"
                "Once the file exists at that path, it will render here automatically — "
                "no code changes needed."
            )
        if st.button("Close preview", icon=":material/close:"):
            st.session_state.open_dashboard = None
            st.rerun()
