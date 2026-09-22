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
  studies.py                     # Searchable/filterable studies catalogue
  dashboards.py                  # Dashboard catalogue + inline HTML viewer
  fieldwork.py                   # Full MSU/DIF + fieldwork history (detail page)
  weekly.py                      # Weekly digest - major changes & recommended next steps
  about.py                       # Scope, privacy, roadmap
modules/
  data_loader.py                 # ALL data access goes through here - week-scoped and
                                  #   full-history loaders, filter helpers, graceful
                                  #   fallback logic
  snowflake_client.py            # Real Snowflake connector (in-app reviews & feedback) -
                                  #   every function returns (data, error), never raises
  surveymonkey_client.py         # SurveyMonkey v3 API connector - UNTESTED, see below
  refresh_state.py               # Tracks last-successful-refresh per source (data/refresh_meta.json)
  styles.py                      # Jeeny brand colors/logos + shared UI helpers (incl. esc()
                                  #   for HTML-escaping data-derived text)
scripts/
  refresh_snowflake_data.py      # Standalone script: pulls Snowflake data, writes it atomically
  refresh_surveymonkey_data.py   # Standalone script: discovers/refreshes SurveyMonkey surveys
.github/workflows/
  refresh_snowflake.yml          # Scheduled (every 6h) + manual - runs the Snowflake script
  refresh_surveymonkey.yml       # Scheduled (every 6h) + manual - runs the SurveyMonkey script
data/
  studies.json                   # Studies Library content
  dashboards.json                # Dashboard catalogue content (curated + auto-discovered, see below)
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
  generated/                     # Auto-discovered generated dashboards (see below) - drop a
                                  #   <slug>.html + <slug>.meta.json pair here, no code change
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
  numeric `surveymonkey_id`, and generated dashboards are matched by the
  `id` field in their `meta.json`.
- Both scheduled scripts write atomically (`tempfile.mkstemp` +
  `os.replace`) and leave existing files untouched on failure, so a failed
  run never corrupts or half-writes the data the deployed app is reading.

## Adding your real content

Everything else you need to replace lives in `/data` and `/dashboard_files`
— no code changes required for routine updates.

### Add or edit a study

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
  rendered in the UI, including in AI-written summaries.
- Mask any personal identifiers before adding them to `data/*.json`.
- Real Snowflake and SurveyMonkey credentials never live in this repo — they
  go in GitHub Actions repository secrets and/or `.streamlit/secrets.toml`
  (gitignored). Only `.streamlit/secrets.toml.example`, with placeholder
  values, is committed.
- The sidebar carries a persistent "Internal use only" label on every page.

## What's intentionally out of scope

- User login / permissions
- A live Power BI connection (dashboards are either bundled HTML exports or
  auto-discovered generated files — see above)
- AI-generated answers or a chatbot beyond the scheduled dashboard-generation
  Routine described above
- Action-management / task tracking
