"""Fieldwork & Quality - full history of MSU/DIF sessions and fieldwork completions."""

import streamlit as st

from modules import data_loader as dl
from modules import styles

styles.page_title("Fieldwork & Quality")
st.caption("Full history - mystery-shopper (MSU) and driver in-field (DIF) sessions, plus fieldwork completions")

fcol1, fcol2 = st.columns(2)
with fcol1:
    market = st.selectbox("Market", options=dl.MARKETS, key="selected_market")
with fcol2:
    audience = st.selectbox("Audience", options=dl.AUDIENCES, key="selected_audience")

st.divider()

st.markdown("#### Fieldwork completed")
fieldwork = dl.load_fieldwork_all(market, audience)
if not fieldwork:
    st.caption("No fieldwork records match the selected filters.")
else:
    rows_html = "".join(
        styles.compact_html(f"""
        <tr>
          <td><strong>{styles.esc(item.get('study') or 'Untitled study')}</strong></td>
          <td>{styles.esc(item.get('market') or '—')}</td>
          <td>{styles.esc(item.get('audience') or '—')}</td>
          <td style="font-size:12px;color:{styles.TEXT_MUTED};">{styles.esc(item.get('week_id') or '—')}</td>
          <td style="font-size:12px;color:{styles.TEXT_MUTED};">{styles.esc(item.get('completion_date') or '—')}</td>
          <td>{f'<a href="{item["report_url"]}" target="_blank" rel="noopener">Open</a>' if item.get('report_url') else f'<span style="color:{styles.COOL_GRAY};">—</span>'}</td>
        </tr>
        """)
        for item in fieldwork
    )
    st.markdown(
        styles.compact_html(f"""
        <table class="jih-table">
          <thead><tr><th>Study</th><th>Market</th><th>Audience</th><th>Week</th><th>Completed</th><th>Report</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """),
        unsafe_allow_html=True,
    )

st.divider()

st.markdown("#### MSU / DIF quality")
perf_rows = dl.load_msu_dif_performance_all(market)
if not perf_rows:
    st.caption("No MSU / DIF sessions match the selected filters.")
else:
    rows_html = "".join(
        styles.compact_html(f"""
        <tr>
          <td style="font-size:12px;color:{styles.TEXT_MUTED};">{styles.esc(r['week_id'])}</td>
          <td><strong>{styles.esc(r['name'])}</strong> &ndash; {styles.esc(r['role'])}<br/>
              <span style="color:{styles.TEXT_MUTED};font-size:12px;">{styles.esc(r['city'])}</span></td>
          <td>{r['completed']}</td>
          <td>{r['quality'] if r['quality'] is not None else '-'}</td>
          <td>{styles.status_pill_html(r['status'])}</td>
        </tr>
        """)
        for r in perf_rows
    )
    st.markdown(
        styles.compact_html(f"""
        <table class="jih-table">
          <thead><tr><th>Week</th><th>Shopper / Driver</th><th>Completed</th><th>Quality</th><th>Status</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """),
        unsafe_allow_html=True,
    )
    styles.sample_data_caption()

st.divider()
st.page_link("views/home.py", label="Back to Home", icon=":material/home:")
