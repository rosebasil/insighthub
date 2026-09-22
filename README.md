# Jeeny Insights Hub

Internal Streamlit app that brings Jeeny's research studies, dashboards, and
weekly insights summaries into one searchable place. **For internal use
only.**

Two real data sources are wired up: **Snowflake** (Jeeny's in-app reviews &
feedback, `JEENY_PROD.GENERAL.FEEDBACKEVENTS`) and **SurveyMonkey** (survey
discovery and response counts). Both refresh on a schedule via GitHub
Actions and write to files in `/data` that the deployed app reads — nothing
requires a manual JSON edit for routine updates. See "Connecting real data
sources" below for exactly what's live, what's still blocked, and the
one-time admin actions needed to finish activating each one.

On top of those two, the **research register** (`data/research_register.json`
+ `dashboard_files/runs/`) is a general publishing pipeline for *any*
recurring or ad hoc research topic — weekly/biweekly SurveyMonkey studies,
biweekly Snowflake analyses, and anything added later. See "The research
register & publishing pipeline" below for how a topic's periodic output
(from a script, a scheduled Claude chat, or a person) shows up in the
Studies Library automatically.

## Requirements

- Python 3.10+

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run Home.py
```

Streamlit will open the app in your browser (default: http://localhost:8501).
The sidebar navigation gives you: **Home, Studies Library, Dashboards,
Fieldwork & Quality, Weekly Summary, About**.

## Project structure

```
Home.py                          # entry point - sets up navigation (st.navigation)
views/
  home.py                        # Home - search, week/market/audience filters, summary
                                  #   cards, cohort highlights, in-app reviews & feedback,
                                  #   survey tracker, fieldwork & quality (compact), recent
                                  #   studies/dashboards
  studies.py                     # Studies Library: topic -> reporting runs -> files (the
                                  #   research register) + "Add ad hoc study" + legacy catalogue
  dashboards.py                  # Dashboard catalogue + inline HTML viewer
  fieldwork.py                   # Full MSU/DIF + fieldwork history (detail page)
  weekly.py                      # Weekly digest - major changes & recommended next steps
  about.py                       # Scope, privacy, roadmap
modules/
  data_loader.py                 # ALL data access for Home/Dashboards/Fieldwork/Weekly goes
                                  #   through here - week-scoped and full-history loaders,
                                  #   filter helpers, graceful fallback logic
  register.py                    # The research register + run manifests (topic catalogue +
                                  #   discover_runs()) - framework-agnostic, used by both
                                  #   views/studies.py and standalone scripts/ - see below
  snowflake_client.py            # Real Snowflake connector (in-app reviews & feedback, plus
                                  #   no-rides-after-signup) - every function returns
                                  #   (data, error), never raises
  surveymonkey_client.py         # SurveyMonkey v3 API connector - UNTESTED, see below
  drive_client.py                # Google Drive connector (service-account, NOT the claude.ai
                                  #   chat connector) for the run-publishing pipeline - see below
  claude_client.py               # Optional "Analyze with Claude" helper for the ad hoc study
                                  #   form (Anthropic API, separate from Drive/Snowflake)
  refresh_state.py               # Tracks last-successful-refresh per source (data/refresh_meta.json)
  styles.py                      # Jeeny brand colors/logos + shared UI helpers (incl. esc()
                                  #   for HTML-escaping data-derived text)
scripts/
  refresh_snowflake_data.py      # Standalone script: pulls Snowflake feedback data, writes it atomically
  refresh_surveymonkey_data.py   # Standalone script: discovers/refreshes SurveyMonkey surveys
  run_no_rides_after_signup.py   # Standalone script: biweekly no-rides-after-signup run -> register
  run_in_app_reviews_report.py   # Standalone script: biweekly in-app-reviews report run -> register
  sync_drive_runs.py             # Standalone script: mirrors the shared Drive folder into
                                  #   dashboard_files/runs/ for the register to discover
.github/workflows/
  refresh_snowflake.yml            # Scheduled (every 6h) + manual - Snowflake feedback refresh
  refresh_surveymonkey.yml         # Scheduled (every 6h) + manual - SurveyMonkey refresh
  run_no_rides_after_signup.yml    # Scheduled (Mondays) + manual - no-rides-after-signup run
  run_in_app_reviews_report.yml    # Scheduled (Mondays) + manual - in-app-reviews report run
  sync_drive_runs.yml              # Scheduled (every 3h) + manual - Drive -> register sync
data/
  studies.json                   # Legacy narrative studies catalogue (pre-dates the register)
  dashboards.json                # Dashboard catalogue content (curated + auto-discovered, see below)
  research_register.json         # The workflow catalogue (topics) - see "research register" below
  highlights.json                # Per-cohort highlights, by week (DX_KSA/DX_JOR/PAX_KSA/PAX_JOR)
  surveys.json                   # Surveys, by week (sent/responses/linked dashboard/status)
  issues.json                    # WhatsApp & technical issues log, by week
  msu_dif_performance.json       # MSU (mystery shopper) & DIF (driver in-field) fieldwork, by week
  fieldwork.json                 # Fieldwork completions, by week
  weekly_digest.json             # Major changes & recommended next steps, by week
  sentiment_summary.json         # Weekly in-app review/feedback headline metrics, by cohort - real
                                  #   Snowflake data (see below), refreshed on a schedule
  sentiment_themes.json          # Weekly theme mention counts, by cohort, for the trend chart
  refresh_meta.json              # Last refresh status per source - powers the Home page's
                                  #   "Last successful refresh" indicator
dashboard_files/
  driver_voice_radar.html        # Sample embedded dashboard (demo)
  generated/                     # Auto-discovered generated dashboards (legacy path, see below) -
                                  #   drop a <slug>.html + <slug>.meta.json pair here, no code change
  runs/                          # The research register's run manifests + output files, one
                                  #   subfolder per workflow_id - see "research register" below
docs/
  PUBLISH_TO_INSIGHTS_HUB.md     # Copy-paste instruction block for your existing Claude chats
                                  #   / Cowork tasks / Project instructions - see below
assets/
  logo-passenger.png             # full Jeeny logo, pink - passenger brand
  logo-driver.png                # full Jeeny logo, purple - driver brand
  icon-passenger.png             # cropped glyph-only version (pink)
  icon-driver.png                # cropped glyph-only version (purple)
.streamlit/
  config.toml                    # Jeeny pink theme
  secrets.toml.example           # Template for local credentials (copy to secrets.toml, gitignored)
requirements.txt
```

Weeks are **not** a data file — `data_loader.load_weeks()` generates the
last 26 weeks plus 1 upcoming week automatically, anchored to the
Sunday–Saturday convention (`_most_recent_sunday()`), so a new reporting
week appears on its own every Sunday with no edit required.

### Brand colors and logos

Colors are sampled directly from the real logo files (not guessed): pink
`#EC008C` and purple `#662D91`, plus dark navy, lime green and cool gray from
the wider Jeeny palette (`modules/styles.py`). This app serves both driver
(DX) and passenger (PAX) audiences internally, so **purple leads** (sidebar
accent, buttons, DX badges/highlight cards) and **pink is used sparingly** to
mark PAX-specific content (PAX badges/highlight cards) - pink and purple are
never given equal weight in the same view. The sidebar brand mark uses the
full purple logo. To update the logos, replace the PNG files in `/assets`
(keep the same filenames) — no code changes needed.

Every place that needs an exact brand color renders through small HTML-snippet
helpers in `modules/styles.py` (`audience_badge_html`, `cohort_badge_html`,
`status_pill_html`, `stat_tile_html`, `issue_card_html`, `bar_html`,
`sentiment_mix_html`, `delta_badge_html`) rather than Streamlit's built-in
`st.badge`/`st.metric`, whose fixed color palette doesn't include Jeeny pink
or purple. **Every one of these helpers escapes data-derived text with
`styles.esc()` before interpolating it into HTML** — any new HTML snippet
that embeds a value read from `data/*.json` (or from Snowflake/SurveyMonkey)
must do the same, since that text is rendered with `unsafe_allow_html=True`.
If you add a new HTML snippet, also pass it through `styles.compact_html()`
before concatenating it with others - see the docstring on that function for
why (a whitespace-only line inside a raw-HTML block silently breaks
Streamlit's Markdown rendering).

## Connecting real data sources

### Snowflake — in-app reviews & feedback (partially live)

**What's real today:** `modules/snowflake_client.py` queries
`JEENY_PROD.GENERAL.FEEDBACKEVENTS` directly — this is Jeeny's own in-app
rating/feedback event log, covering both drivers and passengers across KSA
and Jordan. It is **not** app-store or social-media data, and the app never
labels it that way. The query buckets events into Sunday–Saturday weeks
(verified against this account's actual `DAYOFWEEK()` indexing — Sunday=1
here, not the commonly-assumed 0), and only ever runs aggregate/count
queries — no `USER_MOBILE_NUMBER`, `USER_NAME`, or raw comment text is ever
selected, so no personal identifier reaches this repo or the UI.

`data/sentiment_summary.json` and `data/sentiment_themes.json` currently
hold a real one-time snapshot (237 rows) pulled directly from Snowflake for
the 6 weeks ending 2026-09-20, using the exact same queries
`snowflake_client.py` and `scripts/refresh_snowflake_data.py` run. This is
real Jeeny data, not a sample — but it was a manual pull, not the automated
path, so `data/refresh_meta.json` honestly records its status as
`manual_snapshot`, not `ok`, and the Home page's "Last successful refresh"
correctly shows "Never" until the automated path below runs at least once.

**What's blocked — the one-time request for your Snowflake administrator:**

1. Create (or reuse) a **service account** with a role scoped to read
   `JEENY_PROD.GENERAL.FEEDBACKEVENTS` (`SELECT` only — no write access is
   needed).
2. Grant that role `USAGE` on the warehouse it should run queries on.
3. Hand back: **account identifier, username, password** (or a key pair for
   key-pair auth), the **role name**, and the **warehouse name**.
4. Add those as GitHub Actions repository secrets (Settings → Secrets and
   variables → Actions): `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
   `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`. The
   scheduled workflow (`.github/workflows/refresh_snowflake.yml`, every 6
   hours + manual dispatch) will start committing real refreshed data the
   next time it runs — no further code change needed.
5. For local development, or a deployed app that queries Snowflake directly
   instead of relying on the file the workflow commits, copy
   `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (gitignored)
   and fill in the same five values under `[snowflake]`.

Once credentials exist anywhere (env vars for the script, `st.secrets` for
the live app), no other change is needed — `modules/data_loader.py` already
prefers a live Snowflake query and only falls back to the JSON files when
Snowflake isn't reachable or isn't configured.

### SurveyMonkey — survey discovery & response counts (built, blocked)

`modules/surveymonkey_client.py` and `scripts/refresh_surveymonkey_data.py`
are written against SurveyMonkey's documented v3 REST API (pagination,
Bearer auth, per-survey response counts) but **could not be tested against
a real account** — no SurveyMonkey MCP connector or API token was available
while building this. Treat it as a well-informed draft: the first real run
should be treated as a test, not a production cutover, since an endpoint
that moved or a field that got renamed will only surface against the real
API.

**The one-time request for whoever administers Jeeny's SurveyMonkey
account:**

1. Create (or reuse) an OAuth app / access token with scopes
   `surveys_read` and `responses_read`.
2. Hand the resulting access token to whoever manages this repo's secrets.
3. Add it as a GitHub Actions repository secret:
   `SURVEYMONKEY_ACCESS_TOKEN`. The scheduled workflow
   (`.github/workflows/refresh_surveymonkey.yml`, every 6 hours + manual
   dispatch) will then discover every survey visible to that token,
   register any new one as a **draft** row in `data/surveys.json`
   (`status: "draft"`, `week_id: null`) — drafts never appear in the Home
   page's survey tracker — and refresh response counts for surveys a human
   has already published (set a `week_id`, `reporting_period`, and
   `dashboard_id` on the draft, flip `status` to `"published"`, and it
   appears automatically).
4. For local dev, add `access_token` under `[surveymonkey]` in
   `.streamlit/secrets.toml`.
5. **Run the script by hand once** after the token is added
   (`python scripts/refresh_surveymonkey_data.py`) and fix whatever the
   real API returns differently from what's assumed — `_request()` in
   `surveymonkey_client.py` returns verbose errors (status code + response
   body) specifically to make that fast.

### Auto-generated weekly dashboards (live)

`modules/data_loader.discover_generated_dashboards()` scans
`dashboard_files/generated/` for `<slug>.html` + `<slug>.meta.json` pairs
every time the Dashboards list is loaded — no `data/dashboards.json` edit
required. A meta file must include `id`, `title`, `generated_at`, and
`week_id`; anything missing a required field, whose HTML file is missing, or
whose `id` collides with another generated dashboard is flagged
`needs_review` and never silently shown. Whatever writes a new dashboard
here (a scheduled Claude session, a script, a person) just needs a stable,
unique `id` per report — the app picks it up on the next page load.

A recurring Claude Code Routine is configured to generate and drop a new
weekly dashboard into this folder on a schedule (see the "Reports appear
automatically" note in the final verification report for this build) — this
is the "no one has to upload the same report by hand each week" mechanism.
One caveat: the Routine's fired sessions do not currently inherit this
session's Snowflake MCP connector grant (a platform limitation, not a config
bug), so until that's resolved a fired session can build a dashboard from
whatever's already on disk (`data/*.json`, the real Snowflake snapshot) but
can't run a fresh live Snowflake query itself.

### The research register & publishing pipeline

This is the general mechanism behind "every recurring or ad hoc study
shows up in the Studies Library automatically" - it's what
`wf-in-app-reviews` and `wf-no-rides-after-signup` (below) and the ad hoc
study form both publish through, and it's designed so a Claude chat or
Cowork task can publish into it too, without ever touching this repo
directly.

**Two files:**

- `data/research_register.json` - the topic catalogue. One row per
  recurring or ad hoc topic: `id`, `topic`, `owner`, `source`
  (`SurveyMonkey`/`Snowflake`/`Mixed`/`Manual`), `cadence`
  (`weekly`/`biweekly`/`on-demand`), `market`, `audience`,
  `claude_reference` (a chat/task URL or name, or `null`), `readiness_rule`
  (plain text - when this topic's next period is actually safe to report),
  `preferred_formats`, and `status`.
- `dashboard_files/runs/<workflow_id>/<run_id>.meta.json` (+ its output
  file(s), same folder) - one manifest per completed run. Required fields:
  `run_id`, `workflow_id`, `topic`, `source`, `owner`, `cadence`,
  `period_start`, `period_end`, `data_as_of`, `status`
  (`published`/`failed`/`needs_review`), and `files` (a list of
  `{format, path}`, `format` one of `dashboard_html`/`pptx`/`docx`/`pdf`/`link`).
  See `modules/register.py`'s module docstring and `_RUN_REQUIRED_FIELDS`
  for the exact schema, and `docs/PUBLISH_TO_INSIGHTS_HUB.md` for a
  ready-to-paste description of it.

`modules/register.discover_runs()` scans that folder tree on every page
load - a manifest missing a required field, pointing at a file that
doesn't exist, or reusing another run's `run_id` is returned under
`needs_review` and never shown as published (visible in a "N run(s) need
review" expander at the bottom of the Studies Library). A revised run
(same `run_id`, re-published) replaces the old one rather than
duplicating - `run_id` should encode the period so re-runs are naturally
idempotent (e.g. `wf-no-rides-after-signup-2026-08-23`).

**Three ways a run gets published:**

1. **A standalone script**, entirely inside GitHub Actions, no Claude
   chat involved - `scripts/run_no_rides_after_signup.py` and
   `scripts/run_in_app_reviews_report.py` are the two live examples:
   query Snowflake, build an HTML report, call
   `modules/register.save_run()`. Use this pattern for any workflow
   Snowflake alone can fully answer.
2. **The "Add ad hoc study" form** in the Studies Library - manual entry
   (title, objective, owner, date, market, audience, findings, source)
   plus a file upload or report link, calling the same `save_run()`.
   Works completely without Claude; an optional "Analyze with Claude"
   button offers a short synthesis if `[anthropic]` is configured (see
   below) - never required.
3. **A Claude chat or Cowork task with the Drive connector**, for
   workflows that need a chat's judgment (SurveyMonkey analysis, anything
   Snowflake alone can't answer). See "Google Drive - the chat-publishing
   pipeline" below and `docs/PUBLISH_TO_INSIGHTS_HUB.md` for the exact
   instruction to paste into that chat/task.

### Google Drive - the chat-publishing pipeline (built, blocked)

**Important distinction:** the "Google Drive" connector you can turn on
inside a claude.ai chat lets *that chat* read/search/upload Drive files
during the conversation - it has no way to reach this deployed app. This
app instead uses a second, independent Drive connection: a Google Cloud
**service account** (`modules/drive_client.py`), authenticated with its
own credentials, that only this app and `scripts/sync_drive_runs.py` use
to read files back out of a shared folder. A chat's Drive connector and
this service account happen to point at the same folder; they are
otherwise unrelated systems. Currently **not connected** - no Drive
credentials are configured in this environment.

**The one-time setup:**

1. In Google Cloud Console, create a **service account** and download its
   JSON key (IAM & Admin → Service Accounts → your account → Keys → Add
   key → JSON).
2. Create (or reuse) a **shared Drive folder** for published runs, and
   **share it with the service account's email**
   (`name@project.iam.gserviceaccount.com`, found in the key JSON) -
   Viewer access is enough, since this app only reads.
3. Add two GitHub Actions repository secrets: `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`
   (the entire key JSON, as one string) and `GOOGLE_DRIVE_FOLDER_ID` (the
   folder's id, from its URL). The scheduled workflow
   (`.github/workflows/sync_drive_runs.yml`, every 3 hours + manual
   dispatch) will start mirroring it into `dashboard_files/runs/`.
4. For local dev, or a deployed app reading Drive directly, add the same
   two values under `[google_drive]` in `.streamlit/secrets.toml` (see
   `.streamlit/secrets.toml.example`).
5. **Also share the same folder** (and enable the Drive connector) with
   every Claude chat/Cowork task that should publish into it, and paste
   `docs/PUBLISH_TO_INSIGHTS_HUB.md`'s instruction block into each one's
   Project instructions or task prompt.

**What Claude Code cannot do here:** this session has no way to list,
read, or edit your claude.ai chats, projects, or Cowork tasks - they're a
separate product surface with no tool this session can reach. Identifying
which of your existing chats/tasks run which recurring study, and pasting
the publish instruction into them, needs to happen from your side. Every
row in `data/research_register.json` that doesn't yet have a
`claude_reference` says so explicitly (`claude_reference_note`) instead
of silently leaving it blank.

### No Rides After Sign-Up (Passengers) - business definition

Confirmed with the hub's owner on 2026-09-22, not invented - the real
columns were inspected via `INFORMATION_SCHEMA` first (see
`modules/snowflake_client.py`'s comment above `fetch_no_rides_after_signup`):

- **Audience:** passengers only.
- **Signup event:** `PASSENGERS.VPASSENGERSPROFILE.SIGNUPDATE`.
- **First-ride definition:** `FIRSTRIDE` (a *completed* ride) - not
  `FIRSTREQUEST`, which is only a request and may never convert.
- **Window:** 14 days after `SIGNUPDATE`.
- **"No ride":** `FIRSTRIDE IS NULL` once the full 14-day window has
  elapsed. A period only counts once `period_end + 14 days <= today`
  (`modules/register.is_period_ready()`) - counting a signup before its
  window closes would understate the no-ride rate.
- **Eligibility (data hygiene, not a business choice):** `PHONECOUNTRYCODE
  IN ('SA', 'JO')`, `ISTEST` excluded.

If this definition ever needs to change (a different window, including
drivers, a different first-ride definition), update both
`modules/snowflake_client.py`'s query and `scripts/run_no_rides_after_signup.py`'s
docstring together, and record who confirmed the change and when in
`data/research_register.json`'s `business_definition.confirmed_by`.

### Analyze with Claude (optional, ad hoc studies only)

The "Add ad hoc study" form's "Analyze with Claude" button calls the
Anthropic API directly (`modules/claude_client.py`) to offer a short
synthesis of the objective/findings you typed - entirely optional, and
the form saves with or without it. Add an API key under `[anthropic]` in
`.streamlit/secrets.toml` (see `.streamlit/secrets.toml.example`) to
enable it; without one, the button is replaced with a plain "not
configured" note.

### Refresh status, error reporting, and deduplication

- `data/refresh_meta.json` records `status` (`ok`/`error`/`manual_snapshot`),
  a human-readable `message`, `rows_written`, and `checked_at` per source.
  `modules/refresh_state.latest_successful_refresh()` — shown on the Home
  page header — only counts a source once it reports `ok`, so a manual
  snapshot or a source that's never run never falsely claims to be live.
- Every external-data function (`snowflake_client.py`,
  `surveymonkey_client.py`) returns `(data, error)` and never raises, so a
  bad credential, a network failure, or an empty result degrades the
  relevant section of the UI instead of crashing the page.
- Deduplication is by the source's own stable ID, never by name or position:
  Snowflake rows are recomputed per (week, cohort) range query (idempotent —
  re-running never double-counts), SurveyMonkey surveys are matched by their
  numeric `surveymonkey_id`, generated dashboards are matched by the `id`
  field in their `meta.json`, and research-register runs are matched by
  their `run_id` (`modules/register.discover_runs()` — a re-published
  `run_id` replaces the prior run instead of duplicating it).
- Both scheduled scripts write atomically (`tempfile.mkstemp` +
  `os.replace`) and leave existing files untouched on failure, so a failed
  run never corrupts or half-writes the data the deployed app is reading.

## Adding your real content

Everything else you need to replace lives in `/data` and `/dashboard_files`
— no code changes required for routine updates.

**For a new ad hoc study, use the "+ Add ad hoc study" form in the Studies
Library instead of editing `data/studies.json` by hand** — it writes into
the research register through the same path a scheduled script or a
Claude chat uses, so it shows up identically (topic → runs → files),
supports attaching a PPT/DOC/PDF or pasting a report link, and needs no
JSON editing at all. The `data/studies.json` instructions below are kept
for the studies already logged there before the register existed.

### Add or edit a legacy study

Edit `data/studies.json` and add a new object following the existing schema:

```json
{
  "id": "unique-slug",
  "title": "Study Title",
  "description": "One or two sentence summary.",
  "audience": "Driver",                 // "Driver" or "Passenger"
  "country": ["KSA", "Jordan"],
  "research_type": "Survey",            // Survey | Interview | Reviews | Funnel Analysis
  "topic": ["Prices", "App stability"],
  "date": "2026-09-01",                 // YYYY-MM-DD, used for sorting/filtering
  "reporting_period": "Q3 2026",
  "sample_size": 1200,                  // omit if not applicable
  "key_findings": ["Finding 1", "Finding 2"],
  "critical": false,
  "dashboard_id": "matching-dashboard-id-or-empty",
  "report_url": "https://... or leave empty",
  "is_sample_data": false               // set false once this is real data
}
```

### Add or replace a dashboard

1. Export your dashboard as a standalone HTML file.
2. Drop it into `dashboard_files/`, e.g. `dashboard_files/driver_in_app_reviews.html`.
3. Make sure the `file` field in `data/dashboards.json` for that dashboard
   points to the same relative path.
4. Reload the app — the Dashboards page will automatically detect the file
   and embed it instead of showing the placeholder message.

To publish a dashboard without touching `data/dashboards.json` at all
(e.g. from an automated job), drop a `<slug>.html` + `<slug>.meta.json` pair
into `dashboard_files/generated/` instead — see "Auto-generated weekly
dashboards" above.

### Log a cohort highlight

Append to `data/highlights.json`. `cohort` is one of `DX_KSA`, `DX_JOR`,
`PAX_KSA`, `PAX_JOR`. A bullet starting with `"Needs attention:"` is flagged
on the Home page. `dashboard_id` (and optionally `study_id`) links the card
to an "Open" button:

```json
{
  "week_id": "2026-09-27",
  "cohort": "DX_KSA",
  "bullets": [
    "Summary bullet — this becomes the card's main finding.",
    "Needs attention: something that needs follow-up."
  ],
  "dashboard_id": "driver-voice-radar"
}
```

### Log a survey, a WhatsApp/technical issue, or MSU/DIF fieldwork

- `data/surveys.json` — one object per survey per week. `sent` is optional —
  leave it `null` (or omit it) whenever you don't have a verified
  invitations-sent count; the Home page shows "Unverified" instead of
  fabricating a completion percentage. Only `status: "published"` rows
  appear anywhere in the app (`status: "draft"` is how newly-discovered
  SurveyMonkey surveys stay hidden until someone finishes setting them up).
- `data/issues.json` — one object per manually-logged issue
  (`source`: `KSA`/`JO`, `category`: `Tech`/`Feedback`/`Fraud signal`,
  `status`: `New`/`Under review`/`Reported out`/`Closed`). Set
  `reference_type` (`"driver"` or `"passenger"`) and `reference_id` to a
  **masked internal case code** (e.g. `DRV-KSA-88213`) when the issue traces
  back to one person — never a phone number or other real identifier, per
  the Privacy section below. The Home page's "Open critical issues" card
  counts every row across all weeks whose `status` is still open
  (`New`/`Under review`/`Reported out`) — it is intentionally **not**
  scoped to the selected week, and says so on the card.
- `data/msu_dif_performance.json` — `rows` (one per shopper/driver per week)
  plus `meta[week_id]` for the "X of 18 cities live on MSU survey" badge.
- `data/fieldwork.json` — one object per completed piece of fieldwork
  (`study`, `market`, `week_id`, `completion_date`, optional `report_url`
  and `audience`).

### In-app reviews & feedback (Snowflake-backed)

See "Connecting real data sources" above for the full picture. To hand-edit
the offline snapshot instead of waiting on the scheduled refresh,
`data/sentiment_summary.json` is one object per (week, cohort) —
`item_count` and `source`/`last_updated` are required, `rating`,
`rating_count`, `positive_count`/`neutral_count`/`negative_count` are
optional and only render when present. `data/sentiment_themes.json` is one
object per (week, cohort, theme) with a `mentions` count. Kept as two files
on purpose so a week's item volume is never confused with theme-mention
volume (one item can carry more than one theme).

### Edit the Weekly Digest

Edit `data/weekly_digest.json` (one entry per `week_id`, with
`major_changes` and `recommended_areas`). This file is intentionally simple
JSON so it can later be generated automatically by a scheduled job, the same
way generated dashboards already are.

Once you replace sample content with real data, set `"is_sample_data": false`
(or remove the field) so the "Sample data" captions disappear.

## Privacy

- No passenger or driver phone numbers are shown anywhere in the app. Issues
  carry a masked internal case code instead (see above), never a phone
  number.
- The Snowflake connector only ever runs aggregate/count queries — no raw
  comment text or personal identifier is selected, stored in this repo, or
  rendered in the UI, including in AI-written summaries. This includes
  `fetch_no_rides_after_signup()` — it returns per-market counts only,
  never a `PASSENGERID` or row-level record.
- Mask any personal identifiers before adding them to `data/*.json`.
- Files uploaded through the "Add ad hoc study" form, or synced from the
  shared Drive folder, are **not** automatically scanned for personal
  identifiers — whoever uploads a PPT/DOC/PDF/HTML file is responsible for
  making sure it doesn't contain one, the same as any other file added to
  this repo.
- Real Snowflake and SurveyMonkey credentials never live in this repo — they
  go in GitHub Actions repository secrets and/or `.streamlit/secrets.toml`
  (gitignored). Only `.streamlit/secrets.toml.example`, with placeholder
  values, is committed.
- The sidebar carries a persistent "Internal use only" label on every page.

## What's intentionally out of scope

- User login / permissions
- A live Power BI connection (dashboards are either bundled HTML exports or
  auto-discovered generated files — see above)
- Claude Code reading your claude.ai chats, projects, or Cowork tasks
  directly — no tool in this environment can reach them; publishing from
  a chat goes through the Drive pipeline above instead
- Action-management / task tracking
