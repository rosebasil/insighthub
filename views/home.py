"""Home - Insights Overview."""

from datetime import datetime

import streamlit as st

from modules import styles
from modules.data_loader import (
    COHORT_LABELS,
    COHORTS,
    SOURCE_TYPE_LABELS,
    SOURCE_TYPES,
    current_week_id,
    get_week,
    issue_status_counts,
    load_dashboards,
    load_fieldwork,
    load_highlights,
    load_issues,
    load_msu_dif_performance,
    load_sentiment_summary,
    load_studies,
    load_surveys,
    load_theme_trend,
    load_weeks,
    search_all,
    top_themes_with_delta,
)

styles.page_title("Jeeny Insights Hub")
st.caption("Passenger, driver, and market insights — in one place")

# --- Search --------------------------------------------------------------
query = st.text_input(
    "Search",
    placeholder="🔍  Search: prices, app stability, payment, flights, NPS...",
    label_visibility="collapsed",
)

if query:
    results = search_all(query)
    total = len(results["studies"]) + len(results["dashboards"])
    st.write(f"**{total} result(s) for \"{query}\"**")

    for s in results["studies"]:
        with st.container(border=True):
            c1, c2 = st.columns([1, 12], vertical_alignment="center")
            with c1:
                st.image(str(styles.AUDIENCE_ICON[s["audience"]]), width=26)
            with c2:
                st.markdown(f"**{s['title']}**")
                st.caption(s["description"])

    for d in results["dashboards"]:
        with st.container(border=True):
            st.markdown(f"**{d['title']}** · :material/bar_chart:")
            st.caption(d["description"])

    if total == 0:
        st.info("No matches yet — try another keyword.")

    st.divider()

# --- Week picker -----------------------------------------------------------
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
start_dt = datetime.strptime(week["start_date"], "%Y-%m-%d")
end_dt = datetime.strptime(week["end_date"], "%Y-%m-%d")
# "%-d" (no leading zero) is a glibc-only strftime extension and raises
# ValueError on Windows, so build the "Mon D" string manually instead.
start = f"{start_dt.strftime('%b')} {start_dt.day}"
end = f"{end_dt.strftime('%b')} {end_dt.day}"
with top_l:
    st.markdown(f"#### {week['label']}")
    st.caption(f"{start} – {end}")

# --- Stat tiles --------------------------------------------------------
studies = load_studies()
dashboards = load_dashboards()
week_issues = load_issues(selected_week_id)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(styles.stat_tile_html("Studies · in the library", len(studies)), unsafe_allow_html=True)
with c2:
    st.markdown(styles.stat_tile_html("Dashboards · available", len(dashboards)), unsafe_allow_html=True)
with c3:
    st.markdown(
        styles.stat_tile_html("Critical issues · logged this week", len(week_issues), styles.JEENY_PINK),
        unsafe_allow_html=True,
    )

st.divider()

# --- Cohort highlights ---------------------------------------------------
st.markdown("#### 💡 Highlights")
highlights = load_highlights(selected_week_id)

row1 = st.columns(2)
row2 = st.columns(2)
for col, cohort in zip(row1 + row2, COHORTS):
    bullets = highlights.get(cohort, [])
    with col:
        items = "".join(
            f'<li class="{"needs-attention" if b.lower().startswith("needs attention") else ""}">{b}</li>'
            for b in bullets
        ) or "<li>No highlights logged for this cohort this week.</li>"
        st.markdown(
            styles.compact_html(f"""
            <div class="jih-highlight-card" data-group="{styles.cohort_group(cohort)}">
              <h4>{styles.cohort_badge_html(cohort)}</h4>
              <ul>{items}</ul>
            </div>
            """),
            unsafe_allow_html=True,
        )

st.divider()

# --- Surveys + Issues ------------------------------------------------------
left, right = st.columns([1.1, 1], gap="large")

with left:
    st.markdown("#### 📋 Surveys completed this week")
    surveys = load_surveys(selected_week_id)
    if not surveys:
        st.caption("No surveys logged for this week.")
    else:
        hcols = st.columns([2.6, 1.3, 1.3, 1.8, 1.6])
        for c, label in zip(hcols, ["Survey", "Sent", "Responses", "Completion", ""]):
            c.markdown(f"<span style='font-size:11px;color:{styles.TEXT_MUTED};font-weight:700;text-transform:uppercase;'>{label}</span>", unsafe_allow_html=True)
        for s in surveys:
            rcols = st.columns([2.6, 1.3, 1.3, 1.8, 1.6])
            rcols[0].markdown(f"**{s['name']}**")
            rcols[1].write(f"{s['sent']:,}")
            rcols[2].write(f"{s['responses']:,}")
            rcols[3].markdown(
                styles.bar_html(s["completion_pct"] / 100) + f" {s['completion_pct']}%",
                unsafe_allow_html=True,
            )
            if s.get("dashboard_title") and rcols[4].button(
                "Open dashboard", key=f"survey-open-{s['id']}", use_container_width=True
            ):
                st.session_state.open_dashboard = s["dashboard_id"]
                st.switch_page("views/dashboards.py")

with right:
    st.markdown("#### 💬 WhatsApp & technical issues")
    st.caption("Manually logged from KSA & JO groups this week")
    counts = issue_status_counts(week_issues)
    st.markdown(styles.status_bar_html(counts), unsafe_allow_html=True)
    legend_bits = " &nbsp; ".join(
        f'<span style="color:{styles.STATUS_HEX[s]};">●</span> {s} ({counts.get(s, 0)})'
        for s in styles.ISSUE_STATUS_ORDER
    )
    st.markdown(f'<div style="font-size:11.5px;color:{styles.TEXT_MUTED};margin-bottom:10px;">{legend_bits}</div>', unsafe_allow_html=True)

    if not week_issues:
        st.caption("No issues logged for this week.")
    else:
        cards = "".join(styles.issue_card_html(i) for i in week_issues)
        st.markdown(
            styles.compact_html(f'<div style="max-height:420px;overflow-y:auto;padding-right:4px;">{cards}</div>'),
            unsafe_allow_html=True,
        )

st.divider()

# --- Social sentiment & app reviews + Fieldwork completed ------------------
sent_col, field_col = st.columns([1.3, 1], gap="large")

with sent_col:
    st.markdown("#### 💭 Social sentiment & app reviews")
    source_tabs = st.tabs([SOURCE_TYPE_LABELS[s] for s in SOURCE_TYPES])
    for tab, source_type in zip(source_tabs, SOURCE_TYPES):
        with tab:
            cohort_choice = st.selectbox(
                "Segment",
                options=COHORTS,
                format_func=lambda c: COHORT_LABELS[c],
                key=f"sentiment-cohort-{source_type}",
                label_visibility="collapsed",
            )
            summary = load_sentiment_summary(selected_week_id, cohort_choice, source_type)
            trend = load_theme_trend(selected_week_id, cohort_choice, source_type)
            top_themes = top_themes_with_delta(trend, top_n=5)

            if not summary and not top_themes:
                st.caption("No sentiment data available for this period.")
            else:
                tile_specs = [("Items reviewed", summary.get("item_count") if summary else None)]
                rating = summary.get("rating") if summary else None
                if source_type == "app_reviews" and rating is not None:
                    tile_specs.append(("Rating", f"{rating:.1f} ★"))
                tile_cols = st.columns(len(tile_specs))
                for col, (label, value) in zip(tile_cols, tile_specs):
                    col.markdown(
                        styles.stat_tile_html(label, value if value is not None else "—"),
                        unsafe_allow_html=True,
                    )

                if summary and all(
                    summary.get(k) is not None for k in ("positive_count", "neutral_count", "negative_count")
                ):
                    st.markdown(
                        styles.sentiment_mix_html(
                            summary["positive_count"], summary["neutral_count"], summary["negative_count"]
                        ),
                        unsafe_allow_html=True,
                    )

                if summary:
                    st.caption(
                        f"Source: {summary.get('source') or 'Unknown'} · "
                        f"Updated {summary.get('last_updated') or '—'}"
                    )

                if top_themes:
                    theme_names = [t["theme"] for t in top_themes]
                    chart_data = {"Week": [w["label"] for w in trend]}
                    for name in theme_names:
                        chart_data[name] = [w["themes"].get(name, 0) for w in trend]
                    st.line_chart(chart_data, x="Week", height=220)

                    st.markdown(
                        f"<div style='font-size:12.5px;font-weight:600;color:{styles.JEENY_NAVY};margin-bottom:4px;'>"
                        f"Top themes this week</div>",
                        unsafe_allow_html=True,
                    )
                    theme_rows_html = "".join(
                        styles.compact_html(f"""
                        <tr>
                          <td>{t['theme']}</td>
                          <td>{t['mentions']}</td>
                          <td>{styles.delta_badge_html(t['delta'], t['is_new'])}</td>
                        </tr>
                        """)
                        for t in top_themes
                    )
                    st.markdown(
                        styles.compact_html(f"""
                        <table class="jih-table">
                          <thead><tr><th>Theme</th><th>Mentions</th><th>vs last week</th></tr></thead>
                          <tbody>{theme_rows_html}</tbody>
                        </table>
                        """),
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("No theme data recorded for this week.")

with field_col:
    st.markdown("#### 🔬 Fieldwork completed")
    fieldwork = load_fieldwork(selected_week_id)
    if not fieldwork:
        st.caption("No fieldwork completed this week.")
    else:
        fieldwork_rows_html = ""
        for item in fieldwork:
            if item.get("report_url"):
                report_cell = f'<a href="{item["report_url"]}" target="_blank" rel="noopener">Open &#8599;</a>'
            else:
                report_cell = f'<span style="color:{styles.COOL_GRAY};">—</span>'
            fieldwork_rows_html += styles.compact_html(f"""
            <tr>
              <td><strong>{item.get('study') or 'Untitled study'}</strong></td>
              <td style="color:{styles.TEXT_MUTED};font-size:12.5px;">{item.get('objective') or '—'}</td>
              <td>{item.get('market') or '—'}</td>
              <td style="font-size:12.5px;color:{styles.TEXT_MUTED};">{item.get('completion_date') or '—'}</td>
              <td>{report_cell}</td>
            </tr>
            """)
        st.markdown(
            styles.compact_html(f"""
            <table class="jih-table">
              <thead><tr><th>Study</th><th>Objective</th><th>Market</th><th>Completed</th><th>Report</th></tr></thead>
              <tbody>{fieldwork_rows_html}</tbody>
            </table>
            """),
            unsafe_allow_html=True,
        )

st.divider()

# --- MSU & DIF performance -----------------------------------------------
perf = load_msu_dif_performance(selected_week_id)
head_l, head_r = st.columns([3, 1.6], vertical_alignment="center")
with head_l:
    st.markdown("#### 🧪 MSU & DIF performance")
    st.caption("Volume, quality and automated QC flags")
with head_r:
    st.markdown(
        f'<div style="text-align:right;"><span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};'
        f'color:{styles.JEENY_NAVY};border:1px solid {styles.BORDER_COLOR};">'
        f'{perf["meta"]["cities_live"]} of {perf["meta"]["cities_total"]} cities live on MSU survey</span></div>',
        unsafe_allow_html=True,
    )

if not perf["rows"]:
    st.caption("No MSU / DIF sessions recorded for this week.")
else:
    rows_html = ""
    for r in perf["rows"]:
        if r["min_met"] is True:
            min_met = f'<span style="color:#4C9A5B;font-weight:700;">YES</span>'
        elif r["min_met"] is False:
            min_met = f'<span style="color:#C0392B;font-weight:700;">NO</span>'
        else:
            min_met = f'<span style="color:{styles.COOL_GRAY};">N/A</span>'
        quality = "-" if r["quality"] is None else f"{r['quality']:.1f}"
        rows_html += styles.compact_html(f"""
        <tr>
          <td><strong>{r['name']}</strong> &ndash; {r['role']}<br/>
              <span style="color:{styles.TEXT_MUTED};font-size:12px;">{r['city']} &middot; {r['country']}</span></td>
          <td>{r['completed']}</td>
          <td>{min_met}</td>
          <td>{quality}</td>
          <td>{styles.bar_html(r['spread'] or 0, width_px=70)}</td>
          <td>{r['flags']}</td>
          <td>{styles.status_pill_html(r['status'])}</td>
        </tr>
        """)
    st.markdown(
        styles.compact_html(f"""
        <table class="jih-table">
          <thead>
            <tr><th>Shopper / Driver</th><th>Completed</th><th>Min met</th><th>Quality</th><th>Spread</th><th>Flags</th><th>Status</th></tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        """),
        unsafe_allow_html=True,
    )

st.divider()

# --- Recent studies --------------------------------------------------------
st.markdown("#### 🆕 Recent studies")
recent_studies = sorted(studies, key=lambda s: s["date"], reverse=True)[:3]
cols = st.columns(len(recent_studies)) if recent_studies else []
for col, s in zip(cols, recent_studies):
    with col:
        with st.container(border=True):
            st.image(str(styles.AUDIENCE_ICON[s["audience"]]), width=24)
            st.markdown(f"**{s['title']}**")
            st.caption(f"{s['research_type']} · {s['reporting_period']}")
            if s.get("is_sample_data"):
                styles.sample_data_caption()

st.divider()

quick_l, quick_r = st.columns(2)
with quick_l:
    st.page_link("views/studies.py", label="Browse the Studies Library", icon=":material/library_books:")
with quick_r:
    st.page_link("views/dashboards.py", label="Browse Dashboards", icon=":material/bar_chart:")

st.caption("Jeeny Insights Hub · Internal MVP")
