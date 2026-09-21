"""Jeeny Insights Hub - app entry point and navigation.

Run with:
    streamlit run Home.py
"""

import streamlit as st

from modules import styles

st.set_page_config(
    page_title="Jeeny Insights Hub",
    page_icon=str(styles.ICON_PASSENGER),
    layout="wide",
    initial_sidebar_state="expanded",
)

styles.inject_global_css()

with st.sidebar:
    styles.brand_header()

pages = [
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/studies.py", title="Studies Library", icon=":material/library_books:"),
    st.Page("views/dashboards.py", title="Dashboards", icon=":material/bar_chart:"),
    st.Page("views/weekly.py", title="Weekly Summary", icon=":material/calendar_month:"),
    st.Page("views/about.py", title="About", icon=":material/info:"),
]

st.navigation(pages).run()
