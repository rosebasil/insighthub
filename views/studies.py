"""Studies Library - topic -> reporting runs -> files, plus ad hoc entry.

Every recurring or ad hoc research topic is a row in data/research_register.json
(a "workflow"); every completed run of that topic is a manifest + file(s)
under dashboard_files/runs/<workflow_id>/ (see modules/register.py). This
page discovers both fresh on every load - no data/dashboards.json edit,
no re-upload, ever required to see a new run appear.

Studies logged before this register existed (data/studies.json) still
render further down the page, clearly separated, since migrating their
richer narrative schema (key findings, sample size, etc.) into the
run-manifest shape wasn't worth the risk for this pass.
"""

from __future__ import annotations

import mimetypes
from datetime import date, datetime

import streamlit as st
import streamlit.components.v1 as components

from modules import claude_client, register, styles
from modules.data_loader import dashboard_file_exists, load_dashboards, load_studies

styles.page_title("Studies Library")
st.caption("Browse every recurring and ad hoc research topic - open a run, preview a dashboard, or download a report")

_FORMAT_LABELS = {
    "dashboard_html": "HTML dashboard",
    "pptx": "PowerPoint",
    "docx": "Word doc",
    "pdf": "PDF",
    "link": "Link",
}
_FORMAT_MIME = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}
_UPLOAD_EXT_TO_FORMAT = {"html": "dashboard_html", "htm": "dashboard_html", "pptx": "pptx", "docx": "docx", "pdf": "pdf"}


# --------------------------------------------------------------------------
# Add ad hoc study
# --------------------------------------------------------------------------

with st.expander("+ Add ad hoc study", icon=":material/add_circle:"):
    st.caption("Manual entry works fully without Claude - fill this in and save.")
    with st.form("adhoc_study_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("Title *")
            owner = st.text_input("Owner *", value="rose.alnirab@jeeny.me")
            study_date = st.date_input("Date *", value=date.today())
            source = st.selectbox("Source", options=register.SOURCES, index=register.SOURCES.index("Manual"))
        with c2:
            market = st.selectbox("Market", options=["All", "KSA", "Jordan"])
            audience = st.selectbox("Audience", options=["All", "Driver", "Passenger"])
            uploaded = st.file_uploader("Attach dashboard/PPT/DOC/PDF", type=["html", "htm", "pptx", "docx", "pdf"])
            report_link = st.text_input("...or paste a report link", placeholder="https://...")
        objective = st.text_area("Objective", height=70)
        findings = st.text_area("Findings", height=90)
        submitted = st.form_submit_button("Save ad hoc study", icon=":material/save:")

    if submitted:
        if not title or not owner or not study_date:
            st.error("Title, owner, and date are required.")
        elif not uploaded and not report_link:
            st.error("Attach a file or paste a report link.")
        else:
            workflow_id = f"adhoc-{register.slugify(title)}"
            run_id = f"{workflow_id}-{study_date.isoformat()}"
            now_iso = datetime.now().astimezone().isoformat(timespec="seconds")

            wf_ok, wf_error = register.upsert_workflow(
                {
                    "id": workflow_id,
                    "topic": title,
                    "owner": owner,
                    "source": source,
                    "cadence": "on-demand",
                    "market": market,
                    "audience": audience,
                    "claude_reference": None,
                    "readiness_rule": "Ad hoc - published immediately on submission.",
                    "preferred_formats": [_UPLOAD_EXT_TO_FORMAT.get((uploaded.name.rsplit('.', 1)[-1].lower() if uploaded else ""), "link")],
                    "status": "active",
                }
            )
            if not wf_ok:
                st.error(f"Could not save this topic: {wf_error}")
            else:
                if uploaded:
                    ext = uploaded.name.rsplit(".", 1)[-1].lower()
                    fmt = _UPLOAD_EXT_TO_FORMAT.get(ext, "pdf")
                    file_payloads = [{"format": fmt, "filename": f"{run_id}.{ext}", "content": uploaded.getvalue()}]
                    extra_files = []
                    output_formats = [fmt]
                else:
                    file_payloads = []
                    extra_files = [{"format": "link", "path": report_link}]
                    output_formats = ["link"]

                run_ok, run_error = register.save_run(
                    workflow_id=workflow_id,
                    run_id=run_id,
                    manifest_fields={
                        "topic": title,
                        "source": source,
                        "owner": owner,
                        "cadence": "on-demand",
                        "period_start": study_date.isoformat(),
                        "period_end": study_date.isoformat(),
                        "market": market,
                        "audience": audience,
                        "data_as_of": now_iso,
                        "output_formats": output_formats,
                        "version": 1,
                        "source_references": [],
                        "status": "published",
                        "generated_at": now_iso,
                        "generated_by": "Add ad hoc study form",
                        "objective": objective,
                        "findings": findings,
                        "extra_files": extra_files,
                    },
                    file_payloads=file_payloads,
                )
                if not run_ok:
                    st.error(f"Saved the topic, but the run failed: {run_error}")
                else:
                    st.success(f'Saved "{title}" - it appears in the list below immediately, no page edit needed.')
                    st.session_state["_last_adhoc"] = {"title": title, "objective": objective, "findings": findings}
                    st.rerun()

if st.session_state.get("_last_adhoc"):
    last = st.session_state["_last_adhoc"]
    if claude_client.is_configured():
        if st.button("Analyze this with Claude", icon=":material/auto_awesome:", key="analyze-last-adhoc"):
            with st.spinner("Asking Claude..."):
                analysis, error = claude_client.analyze_ad_hoc_study(last["title"], last["objective"], last["findings"])
            if error:
                st.error(f"Analysis failed: {error}")
            else:
                st.info(analysis)
    else:
        st.caption(
            "Analyze with Claude: not configured. Add an Anthropic API key under "
            "`[anthropic]` in `.streamlit/secrets.toml` to enable this."
        )

st.divider()

# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------

workflows = register.load_register_raw()
discovered = register.discover_runs()
all_runs = discovered["published"]
needs_review = discovered["needs_review"]

with st.expander("Filters", icon=":material/filter_alt:"):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        cadence_filter = st.multiselect("Cadence", options=register.CADENCES)
    with fc2:
        source_filter = st.multiselect("Source", options=register.SOURCES)
    with fc3:
        owner_options = sorted({w["owner"] for w in workflows})
        owner_filter = st.multiselect("Owner", options=owner_options)
    fc4, fc5 = st.columns(2)
    with fc4:
        market_filter = st.multiselect("Market", options=["All", "KSA", "Jordan"])
    with fc5:
        format_filter = st.multiselect(
            "Output type", options=register.OUTPUT_FORMATS, format_func=lambda f: _FORMAT_LABELS.get(f, f)
        )


def _workflow_matches(w: dict) -> bool:
    if cadence_filter and w.get("cadence") not in cadence_filter:
        return False
    if source_filter and w.get("source") not in source_filter:
        return False
    if owner_filter and w.get("owner") not in owner_filter:
        return False
    if market_filter and w.get("market") not in market_filter:
        return False
    if format_filter:
        w_runs = register.runs_for_workflow(w["id"], all_runs)
        run_formats = {f["format"] for r in w_runs for f in r["files"]}
        if not run_formats & set(format_filter):
            return False
    return True


filtered_workflows = [w for w in workflows if _workflow_matches(w)]
st.caption(f"{len(filtered_workflows)} of {len(workflows)} topics")


# --------------------------------------------------------------------------
# Render: topic -> runs -> files
# --------------------------------------------------------------------------


def _run_status_badges(run: dict) -> str:
    status = run.get("status", "needs_review")
    label = "manual snapshot" if "manual" in (run.get("generated_by") or "").lower() and status == "published" else status
    badges = styles.status_pill_html(label)
    return badges


def _render_file(run: dict, f: dict, key_prefix: str) -> None:
    fmt = f["format"]
    label = _FORMAT_LABELS.get(fmt, fmt)
    if fmt == "link":
        st.link_button(f"Open {label}", f["path"], icon=":material/open_in_new:")
        return
    abs_path = f.get("abs_path")
    if not abs_path:
        st.caption(f"{label}: file path missing")
        return
    if fmt == "dashboard_html":
        with st.expander(f"Preview {label}", icon=":material/visibility:"):
            try:
                with open(abs_path, "r", encoding="utf-8") as fh:
                    components.html(fh.read(), height=480, scrolling=True)
            except OSError as exc:
                st.error(f"Could not read file: {exc}")
        try:
            with open(abs_path, "rb") as fh:
                st.download_button(
                    "Download HTML", fh.read(), file_name=f["path"], mime="text/html", key=f"dl-{key_prefix}-{fmt}"
                )
        except OSError:
            pass
    else:
        try:
            with open(abs_path, "rb") as fh:
                content = fh.read()
            mime = _FORMAT_MIME.get(fmt) or mimetypes.guess_type(f["path"])[0] or "application/octet-stream"
            st.download_button(f"Download {label}", content, file_name=f["path"], mime=mime, key=f"dl-{key_prefix}-{fmt}")
        except OSError as exc:
            st.error(f"Could not read file: {exc}")


def _render_run(run: dict, key_prefix: str) -> None:
    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.markdown(f"**{run.get('period_start', '?')} → {run.get('period_end', '?')}**")
        st.caption(f"Data as of {run.get('data_as_of', '—')}")
    with top_r:
        st.markdown(_run_status_badges(run), unsafe_allow_html=True)
    if run.get("objective"):
        st.caption(f"Objective: {run['objective']}")
    if run.get("findings"):
        with st.expander("Findings"):
            st.write(run["findings"])
    for f in run.get("files", []):
        _render_file(run, f, key_prefix)


if not filtered_workflows:
    st.info("No topics match the selected filters.")

for w in filtered_workflows:
    with st.container(border=True):
        head_l, head_r = st.columns([4, 1])
        with head_l:
            st.markdown(f"#### {w['topic']}")
            badges = (
                f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.JEENY_NAVY};'
                f'border:1px solid {styles.BORDER_COLOR};">{styles.esc(w.get("cadence", "on-demand"))}</span>'
                f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.JEENY_NAVY};'
                f'border:1px solid {styles.BORDER_COLOR};">{styles.esc(w.get("source", "Manual"))}</span>'
                f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.JEENY_NAVY};'
                f'border:1px solid {styles.BORDER_COLOR};">{styles.esc(w.get("owner", "—"))}</span>'
            )
            st.markdown(badges, unsafe_allow_html=True)
        with head_r:
            st.markdown(_run_status_badges({"status": w.get("status", "active")}), unsafe_allow_html=True)

        if w.get("claude_reference"):
            st.caption(f"Reference: {w['claude_reference']}")
        elif w.get("claude_reference_note"):
            st.caption(f":material/info: {w['claude_reference_note']}")
        if w.get("readiness_rule"):
            st.caption(f"Readiness: {w['readiness_rule']}")

        w_runs = register.runs_for_workflow(w["id"], all_runs)
        if not w_runs:
            st.caption("No runs published yet.")
        else:
            st.markdown("###### Latest run")
            _render_run(w_runs[0], key_prefix=f"{w['id']}-latest")
            if len(w_runs) > 1:
                with st.expander(f"{len(w_runs) - 1} earlier run(s)"):
                    for i, r in enumerate(w_runs[1:]):
                        _render_run(r, key_prefix=f"{w['id']}-{i}")
                        st.divider()

if needs_review:
    with st.expander(f":material/warning: {len(needs_review)} run(s) need review (not shown above)", icon=":material/warning:"):
        for row in needs_review:
            st.markdown(f"**{styles.esc(row['file'])}**")
            st.caption(styles.esc(row["reason"]))

st.divider()

# --------------------------------------------------------------------------
# Legacy studies.json catalogue (pre-dates the register)
# --------------------------------------------------------------------------

st.markdown("#### Other studies (logged before the register)")
st.caption("Narrative studies with key findings, not yet migrated into the topic/run model above")

legacy_studies = load_studies()
legacy_dashboards = {d["id"]: d for d in load_dashboards()}

lcol1, lcol2, lcol3 = st.columns(3)
with lcol1:
    legacy_audience_filter = st.multiselect("Audience", options=["Driver", "Passenger"], key="legacy-audience")
with lcol2:
    legacy_country_filter = st.multiselect("Country", options=["KSA", "Jordan"], key="legacy-country")
with lcol3:
    legacy_keyword = st.text_input("Keyword", placeholder="e.g. payment, prices, NPS", key="legacy-keyword")


def _legacy_matches(study: dict) -> bool:
    if legacy_audience_filter and study["audience"] not in legacy_audience_filter:
        return False
    if legacy_country_filter and not set(legacy_country_filter) & set(study.get("country", [])):
        return False
    if legacy_keyword:
        haystack = " ".join([study["title"], study["description"], " ".join(study.get("key_findings", []))]).lower()
        if legacy_keyword.lower() not in haystack:
            return False
    return True


legacy_filtered = [s for s in legacy_studies if _legacy_matches(s)]
st.caption(f"{len(legacy_filtered)} of {len(legacy_studies)} studies")

for s in legacy_filtered:
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
        badges += f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.TEXT_MUTED};border:1px solid {styles.BORDER_COLOR};">{styles.esc(" / ".join(s["country"]))}</span>'
        badges += f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.TEXT_MUTED};border:1px solid {styles.BORDER_COLOR};">{styles.esc(s["research_type"])}</span>'
        for t in s.get("topic", []):
            badges += f'<span class="jih-badge" style="background:{styles.BG_LIGHT_GREY};color:{styles.TEXT_MUTED};border:1px solid {styles.BORDER_COLOR};">{styles.esc(t)}</span>'
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

        dash = legacy_dashboards.get(s.get("dashboard_id"))
        if s.get("report_url"):
            st.link_button("Open report", s["report_url"], icon=":material/open_in_new:")
        elif dash:
            st.page_link("views/dashboards.py", label="Open dashboard", icon=":material/bar_chart:")
        else:
            st.button("Not available", disabled=True, key=f"btn-{s['id']}")
