"""Home - Insights Overview."""

from datetime import date, datetime

import streamlit as st

from modules import data_loader as dl
from modules import refresh_state
from modules import register
from modules import styles

styles.page_title("Jeeny Insights Hub")

# --- Search ------------------------------------------------------------
query = st.text_input(
    "Search",
    placeholder="Search: prices, app stability, payment, flights, NPS...",
    label_visibility="collapsed",
)

if query:
    results = dl.search_all(query)
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
            st.markdown(f"**{d['title']}**")
            st.caption(d["description"])

    if total == 0:
        st.info("No matches yet — try another keyword.")

    st.divider()

# --- Week / market / audience filters + last refresh --------------------
weeks = dl.load_weeks()
week_ids_desc = [w["id"] for w in reversed(weeks)]


def _week_label(week_id: str) -> str:
    w = dl.get_week(week_id)
    return f"{w['label']} (current)" if w.get("is_current") else w["label"]


hcol1, hcol2, hcol3, hcol4 = st.columns([2.2, 1, 1, 1.7])
with hcol1:
    selected_week_id = st.selectbox(
        "Reporting week",
        options=week_ids_desc,
        index=week_ids_desc.index(dl.current_week_id()),
        format_func=_week_label,
        key="selected_week_id",
    )
with hcol2:
    market = st.selectbox("Market", options=dl.MARKETS, key="selected_market")
with hcol3:
    audience = st.selectbox("Audience", options=dl.AUDIENCES, key="selected_audience")
with hcol4:
    last_refresh_iso = refresh_state.latest_successful_refresh()
    st.caption("Last successful refresh")
    if last_refresh_iso:
        dt = datetime.fromisoformat(last_refresh_iso)
        st.markdown(f"**{dt.strftime('%b')} {dt.day}, {dt.strftime('%H:%M')} UTC**")
    else:
        st.markdown("**Never**")

week = dl.get_week(selected_week_id)
start_dt = date.fromisoformat(week["start_date"])
end_dt = date.fromisoformat(week["end_date"])
range_label = f"{start_dt.strftime('%b')} {start_dt.day} – {end_dt.strftime('%b')} {end_dt.day}"
filter_bits = [b for b in [market if market != "All" else None, audience if audience != "All" else None] if b]
filter_suffix = f" · Filtered to {' / '.join(filter_bits)}" if filter_bits else ""
st.caption(f"{week['label']} · {range_label}{filter_suffix}")

st.divider()

# --- Four summary cards --------------------------------------------------
studies_all = dl.load_studies()
studies_filtered = dl.studies_matching_filters(studies_all, market, audience)
dashboards_all = dl.load_dashboards()
dashboards_filtered = dl.dashboards_matching_filters(dashboards_all, market, audience)

week_bounds = dl.week_bounds(selected_week_id)
prev_week_id = dl.previous_week_id(selected_week_id)
prev_bounds = dl.week_bounds(prev_week_id) if prev_week_id else None


def _wow_caption(current: int, previous: int | None) -> str:
    if previous is None:
        return ""
    diff = current - previous
    if diff > 0:
        return f"▲ +{diff} vs last week"
    if diff < 0:
        return f"▼ {diff} vs last week"
    return "No change vs last week"


studies_this_week = dl.studies_completed_between(studies_filtered, *week_bounds)
studies_prev_week = dl.studies_completed_between(studies_filtered, *prev_bounds) if prev_bounds else None

surveys_this_week = dl.load_surveys(selected_week_id, market, audience)
responses_this_week = sum(s["responses"] for s in surveys_this_week if s.get("responses") is not None)
if prev_week_id:
    surveys_prev_week = dl.load_surveys(prev_week_id, market, audience)
    responses_prev_week = sum(s["responses"] for s in surveys_prev_week if s.get("responses") is not None)
else:
    responses_prev_week = None

dashboards_this_week = dl.dashboards_updated_between(dashboards_filtered, *week_bounds)
dashboards_prev_week = dl.dashboards_updated_between(dashboards_filtered, *prev_bounds) if prev_bounds else None

open_issues = dl.load_open_issues(market, audience)

card_cols = st.columns(4)
with card_cols[0]:
    st.markdown(
        styles.stat_tile_html("Studies completed this week", len(studies_this_week)),
        unsafe_allow_html=True,
    )
    wow = _wow_caption(len(studies_this_week), len(studies_prev_week) if studies_prev_week is not None else None)
    if wow:
        st.caption(wow)
with card_cols[1]:
    st.markdown(
        styles.stat_tile_html("Survey responses this week", f"{responses_this_week:,}"),
        unsafe_allow_html=True,
    )
    wow = _wow_caption(responses_this_week, responses_prev_week)
    if wow:
        st.caption(wow)
with card_cols[2]:
    st.markdown(
        styles.stat_tile_html("Dashboards updated this week", len(dashboards_this_week)),
        unsafe_allow_html=True,
    )
    wow = _wow_caption(len(dashboards_this_week), len(dashboards_prev_week) if dashboards_prev_week is not None else None)
    if wow:
        st.caption(wow)
with card_cols[3]:
    st.markdown(
        styles.stat_tile_html("Open critical issues", len(open_issues), styles.JEENY_PINK),
        unsafe_allow_html=True,
    )
    st.caption("All-time open backlog, not scoped to this week")

st.divider()

# --- Four cohort highlight cards ------------------------------------------
st.markdown("#### Highlights")
highlights = dl.load_highlights(selected_week_id)
visible_cohorts = [c for c in dl.COHORTS if dl.cohort_matches(c, market, audience)]
dashboards_by_id = {d["id"]: d for d in dashboards_all}
studies_by_id = {s["id"]: s for s in studies_all}

if not visible_cohorts:
    st.caption("No cohorts match the selected market/audience filters.")
else:
    hl_cols = st.columns(len(visible_cohorts)) if len(visible_cohorts) <= 2 else st.columns(2)
    for i, cohort in enumerate(visible_cohorts):
        col = hl_cols[i % len(hl_cols)] if len(visible_cohorts) <= 2 else hl_cols[i % 2]
        entry = highlights.get(cohort, {"bullets": [], "dashboard_id": None, "study_id": None})
        bullets = entry["bullets"]
        main_finding = next((b for b in bullets if not b.lower().startswith("needs attention")), None)
        attention_item = next((b for b in bullets if b.lower().startswith("needs attention")), None)

        body = (
            f'<p style="font-size:13px;color:{styles.TEXT_DARK};margin:4px 0 8px;">{styles.esc(main_finding)}</p>'
            if main_finding
            else f'<p style="font-size:13px;color:{styles.COOL_GRAY};margin:4px 0 8px;">No highlight logged for this cohort this week.</p>'
        )
        if attention_item:
            body += (
                f'<p style="font-size:12.5px;font-weight:600;color:{styles.JEENY_NAVY};margin:0;">'
                f"{styles.esc(attention_item)}</p>"
            )

        with col:
            st.markdown(
                styles.compact_html(f"""
                <div class="jih-highlight-card" data-group="{styles.cohort_group(cohort)}">
                  <h4>{styles.cohort_badge_html(cohort)}</h4>
                  {body}
                </div>
                """),
                unsafe_allow_html=True,
            )
            link_dashboard = dashboards_by_id.get(entry.get("dashboard_id"))
            link_study = studies_by_id.get(entry.get("study_id"))
            if link_dashboard is not None:
                if st.button(f"Open {link_dashboard['title']}", key=f"hl-dash-{cohort}", use_container_width=True):
                    st.session_state.open_dashboard = link_dashboard["id"]
                    st.switch_page("views/dashboards.py")
            elif link_study is not None:
                st.page_link("views/studies.py", label=f"Open {link_study['title']}", icon=":material/library_books:")
    styles.sample_data_caption()

st.divider()

# --- In-app reviews & feedback --------------------------------------------
st.markdown("#### In-app reviews & feedback")
if not visible_cohorts:
    st.caption("No cohorts match the selected market/audience filters.")
else:
    review_cohort = st.selectbox(
        "Segment",
        options=visible_cohorts,
        format_func=lambda c: dl.COHORT_LABELS[c],
        key="review-cohort",
        label_visibility="collapsed",
    )
    result = dl.load_review_feedback(selected_week_id, review_cohort)
    mode = result["mode"]

    if mode == "unavailable":
        st.error(f"{dl.SNOWFLAKE_UNAVAILABLE_MESSAGE}: {result['error']}")
    else:
        summary = result["summary"]
        trend = result["trend"]
        top_themes = dl.top_themes_with_delta(trend, top_n=5)

        if not summary and not top_themes:
            st.caption("No sentiment data available for this period.")
        else:
            tile_specs = [("Themed feedback items", summary.get("item_count") if summary else None)]
            rating = summary.get("rating") if summary else None
            if rating is not None:
                rating_count = summary.get("rating_count")
                rating_label = f"Avg. rating ({rating_count:,} ratings)" if rating_count else "Avg. rating"
                tile_specs.append((rating_label, f"{rating:.2f} ★"))
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

            live_badge = "Live from Snowflake" if mode == "live" else "Scheduled refresh"
            if summary:
                st.caption(f"{live_badge} · Source: {summary.get('source') or 'Unknown'} · Updated {summary.get('last_updated') or '—'}")
            else:
                st.caption(live_badge)

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
                      <td>{styles.esc(t['theme'])}</td>
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
                st.caption("Mentions are counted from Jeeny's own categorized in-app feedback - not AI-written; no AI summary has been generated for this period.")
            else:
                st.caption("No theme data recorded for this week.")

            st.markdown(
                f"<div style='font-size:12.5px;font-weight:600;color:{styles.JEENY_NAVY};margin:14px 0 4px;'>"
                f"Recent complaints</div>",
                unsafe_allow_html=True,
            )
            complaints_result = dl.load_in_app_complaints(selected_week_id, review_cohort)
            complaints_mode = complaints_result["mode"]
            if complaints_mode == "unavailable":
                st.error(f"{dl.SNOWFLAKE_UNAVAILABLE_MESSAGE}: {complaints_result['error']}")
            elif not complaints_result["complaints"]:
                st.caption("No complaint-shaped comments recorded for this cohort this week.")
            else:
                complaints_badge = "Live from Snowflake" if complaints_mode == "live" else "Scheduled refresh"
                st.caption(
                    f"{complaints_badge} · real driver/passenger comments, most recent first - "
                    "internal use only, do not share outside Jeeny"
                )
                for c in complaints_result["complaints"]:
                    ts = (c.get("timestamp") or "")[:16].replace("T", " ")
                    rating_txt = f"{c['rating']}★" if c.get("rating") is not None else "—"
                    with st.container(border=True):
                        head_l, head_r = st.columns([3, 1])
                        with head_l:
                            st.markdown(
                                f"<span style='font-family:monospace;font-size:12px;color:{styles.TEXT_MUTED};'>"
                                f"{styles.esc(c.get('user_id') or '—')}</span> &middot; "
                                f"{styles.esc(c.get('city') or '—')}",
                                unsafe_allow_html=True,
                            )
                        with head_r:
                            st.markdown(
                                f"<span style='float:right;font-size:12px;color:{styles.TEXT_MUTED};'>{rating_txt} · {styles.esc(ts)}</span>",
                                unsafe_allow_html=True,
                            )
                        if c.get("comment_ar"):
                            st.markdown(
                                f"<div dir='rtl' style='font-size:13px;color:{styles.TEXT_DARK};margin:4px 0 2px;'>{styles.esc(c['comment_ar'])}</div>",
                                unsafe_allow_html=True,
                            )
                        if c.get("comment_en"):
                            st.markdown(
                                f"<div style='font-size:12.5px;color:{styles.COOL_GRAY};'>{styles.esc(c['comment_en'])}</div>",
                                unsafe_allow_html=True,
                            )
                st.caption(
                    "Phone numbers are automatically redacted from comment text before display. "
                    "Driver/passenger IDs are internal Jeeny identifiers, not names or phone numbers."
                )

st.divider()

# --- Survey tracker ---------------------------------------------------
st.markdown("#### Survey tracker")
if not surveys_this_week:
    st.caption("No surveys logged for this week matching the current filters.")
else:
    hcols = st.columns([2.2, 1.6, 1.3, 1.3, 1.6, 1.4])
    for c, label in zip(hcols, ["Survey", "Period", "Responses", "Completion", "Report", ""]):
        c.markdown(
            f"<span style='font-size:11px;color:{styles.TEXT_MUTED};font-weight:700;text-transform:uppercase;'>{label}</span>",
            unsafe_allow_html=True,
        )
    for s in surveys_this_week:
        rcols = st.columns([2.2, 1.6, 1.3, 1.3, 1.6, 1.4])
        rcols[0].markdown(f"**{s['name']}**")
        rcols[1].write(s.get("reporting_period") or "—")
        rcols[2].write(f"{s['responses']:,}" if s.get("responses") is not None else "—")
        if s.get("sent") and s.get("completion_pct") is not None:
            rcols[3].markdown(
                styles.bar_html(s["completion_pct"] / 100) + f" {s['completion_pct']}%",
                unsafe_allow_html=True,
            )
        else:
            rcols[3].markdown(f"<span style='color:{styles.COOL_GRAY};'>Unverified</span>", unsafe_allow_html=True)
        rcols[4].write(s.get("dashboard_title") or "—")
        if s.get("dashboard_link_id") and rcols[5].button("Open", key=f"survey-open-{s['id']}", use_container_width=True):
            st.session_state.open_dashboard = s["dashboard_link_id"]
            st.switch_page("views/dashboards.py")
    styles.sample_data_caption()

st.divider()

# --- Recurring workflow status + recent reports ---------------------------
st.markdown("#### Recurring workflow status")
registered_workflows = register.load_register_raw()
all_runs = register.discover_runs()["published"]
if not registered_workflows:
    st.caption("No workflows registered yet.")
else:
    whcols = st.columns([2.4, 1, 1.2, 1.3, 1.8])
    for c, label in zip(whcols, ["Topic", "Cadence", "Source", "Status", "Latest run / next due"]):
        c.markdown(
            f"<span style='font-size:11px;color:{styles.TEXT_MUTED};font-weight:700;text-transform:uppercase;'>{label}</span>",
            unsafe_allow_html=True,
        )
    for w in registered_workflows:
        latest = register.latest_run(w["id"], all_runs)
        wrcols = st.columns([2.4, 1, 1.2, 1.3, 1.8])
        wrcols[0].write(w["topic"])
        wrcols[1].write(w.get("cadence", "—"))
        wrcols[2].write(w.get("source", "—"))
        wrcols[3].markdown(styles.status_pill_html(w.get("status", "active")), unsafe_allow_html=True)
        if latest:
            next_label = register.next_expected_label(w.get("cadence", "on-demand"), latest.get("period_end"))
            wrcols[4].write(f"Through {latest['period_end']} · {next_label}")
        else:
            wrcols[4].write("No runs yet")
    st.page_link("views/studies.py", label="Open Studies Library for full run history", icon=":material/library_books:")

recent_runs = sorted(all_runs, key=lambda r: r.get("generated_at") or "", reverse=True)[:3]
if recent_runs:
    st.markdown("###### Recent reports")
    rr_cols = st.columns(len(recent_runs))
    for col, run in zip(rr_cols, recent_runs):
        with col:
            with st.container(border=True):
                st.markdown(f"**{run.get('topic', run['workflow_id'])}**")
                st.caption(f"{run.get('period_start', '?')} → {run.get('period_end', '?')}")
                fmt_badges = "".join(
                    f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.JEENY_NAVY};'
                    f'border:1px solid {styles.BORDER_COLOR};">{styles.esc(f["format"])}</span>'
                    for f in run.get("files", [])
                )
                st.markdown(fmt_badges, unsafe_allow_html=True)
                st.page_link("views/studies.py", label="Open in Studies Library", icon=":material/arrow_forward:")

st.divider()

# --- Fieldwork and quality (compact, links to detail page) ---------------
st.markdown("#### Fieldwork and quality")
fw_col, perf_col = st.columns([1, 1.2], gap="large")

with fw_col:
    st.markdown("**Fieldwork completed**")
    fieldwork = dl.load_fieldwork(selected_week_id, market, audience)
    if not fieldwork:
        st.caption("No fieldwork completed this week.")
    else:
        rows_html = ""
        for item in fieldwork[:5]:
            report_cell = (
                f'<a href="{item["report_url"]}" target="_blank" rel="noopener">Open</a>'
                if item.get("report_url")
                else f'<span style="color:{styles.COOL_GRAY};">—</span>'
            )
            rows_html += styles.compact_html(f"""
            <tr>
              <td><strong>{styles.esc(item.get('study') or 'Untitled study')}</strong></td>
              <td>{styles.esc(item.get('market') or '—')}</td>
              <td style="font-size:12px;color:{styles.TEXT_MUTED};">{styles.esc(item.get('completion_date') or '—')}</td>
              <td>{report_cell}</td>
            </tr>
            """)
        st.markdown(
            styles.compact_html(f"""
            <table class="jih-table">
              <thead><tr><th>Study</th><th>Market</th><th>Completed</th><th>Report</th></tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
            """),
            unsafe_allow_html=True,
        )
    st.page_link("views/fieldwork.py", label="View full fieldwork & quality history", icon=":material/arrow_forward:")

with perf_col:
    perf = dl.load_msu_dif_performance(selected_week_id, market)
    st.markdown(
        f"**MSU / DIF quality** &nbsp; "
        f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.JEENY_NAVY};'
        f'border:1px solid {styles.BORDER_COLOR};">{perf["meta"]["cities_live"]} of {perf["meta"]["cities_total"]} cities live</span>',
        unsafe_allow_html=True,
    )
    if not perf["rows"]:
        st.caption("No MSU / DIF sessions recorded for this week.")
    else:
        rows_html = ""
        for r in perf["rows"][:5]:
            rows_html += styles.compact_html(f"""
            <tr>
              <td><strong>{styles.esc(r['name'])}</strong> &ndash; {styles.esc(r['role'])}<br/>
                  <span style="color:{styles.TEXT_MUTED};font-size:12px;">{styles.esc(r['city'])}</span></td>
              <td>{r['completed']}</td>
              <td>{r['quality'] if r['quality'] is not None else '-'}</td>
              <td>{styles.status_pill_html(r['status'])}</td>
            </tr>
            """)
        st.markdown(
            styles.compact_html(f"""
            <table class="jih-table">
              <thead><tr><th>Shopper / Driver</th><th>Completed</th><th>Quality</th><th>Status</th></tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
            """),
            unsafe_allow_html=True,
        )
    st.page_link("views/fieldwork.py", label="View full fieldwork & quality history", icon=":material/arrow_forward:")
    styles.sample_data_caption()

st.divider()

# --- Recent studies and dashboards ------------------------------------
st.markdown("#### Recent studies")
recent_studies = sorted(studies_filtered, key=lambda s: s["date"], reverse=True)[:3]
if not recent_studies:
    st.caption("No studies match the selected filters.")
else:
    cols = st.columns(len(recent_studies))
    for col, s in zip(cols, recent_studies):
        with col:
            with st.container(border=True):
                st.image(str(styles.AUDIENCE_ICON[s["audience"]]), width=24)
                st.markdown(f"**{s['title']}**")
                st.caption(f"{s['research_type']} · {s['reporting_period']}")
                if s.get("is_sample_data"):
                    styles.sample_data_caption()

st.markdown("#### Recent dashboards")
recent_dashboards = sorted(dashboards_filtered, key=lambda d: d.get("last_updated") or "", reverse=True)[:3]
if not recent_dashboards:
    st.caption("No dashboards match the selected filters.")
else:
    cols = st.columns(len(recent_dashboards))
    for col, d in zip(cols, recent_dashboards):
        with col:
            with st.container(border=True):
                st.markdown(f"**{d['title']}**")
                owner = d.get("owner") or ("Auto-generated" if d.get("source") == "generated" else "Market Intelligence")
                st.caption(f"{owner} · Updated {d.get('last_updated') or '—'}")
                if d.get("source") == "generated":
                    st.caption(":material/bolt: Auto-generated - no manual JSON edit")
                elif d.get("is_sample_data"):
                    styles.sample_data_caption()
                if st.button("Open", key=f"recent-dash-{d['id']}", use_container_width=True):
                    st.session_state.open_dashboard = d["id"]
                    st.switch_page("views/dashboards.py")

st.divider()

quick_l, quick_r = st.columns(2)
with quick_l:
    st.page_link("views/studies.py", label="Browse the Studies Library", icon=":material/library_books:")
with quick_r:
    st.page_link("views/dashboards.py", label="Browse Dashboards", icon=":material/bar_chart:")

st.caption("Jeeny Insights Hub")
