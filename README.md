# Jeeny Insights Hub (MVP)

Internal Streamlit app that brings Jeeny's research studies, dashboards, and
weekly insights summaries into one searchable place. Version 1: local sample
data only, no live connections, no login. **For internal use only.**

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
The sidebar navigation gives you: **Home, Studies Library, Dashboards, Weekly
Summary, About**.

## Project structure

```
Home.py                         # entry point - sets up navigation (st.navigation)
views/
  home.py                        # Home - week picker, stat tiles, cohort highlights,
                                  #   surveys, WhatsApp/technical issues, social sentiment &
                                  #   app reviews, fieldwork completed, MSU & DIF performance
  studies.py                     # Searchable/filterable studies catalogue
  dashboards.py                  # Dashboard catalogue + inline HTML viewer
  weekly.py                      # Weekly digest - major changes & recommended next steps
  about.py                       # Scope, privacy, roadmap
modules/
  data_loader.py                 # ALL data access goes through here
  styles.py                      # Jeeny brand colors/logos + shared UI helpers
data/
  studies.json                   # Studies Library content
  dashboards.json                # Dashboard catalogue content
  weeks.json                     # Weekly reporting periods (id, label, date range, is_current)
  highlights.json                # Per-cohort highlights, by week (DX_KSA/DX_JOR/PAX_KSA/PAX_JOR)
  surveys.json                   # Surveys completed, by week (sent/responses/linked dashboard)
  issues.json                    # WhatsApp & technical issues log, by week
  msu_dif_performance.json       # MSU (mystery shopper) & DIF (driver in-field) fieldwork, by week
  weekly_digest.json             # Major changes & recommended next steps, by week
  sentiment_summary.json         # Weekly social/app-review headline metrics - EMPTY until you add data
  sentiment_themes.json          # Weekly theme mention counts, for the 6-week trend - EMPTY until you add data
  fieldwork.json                 # Fieldwork completed, by week - EMPTY until you add data
dashboard_files/
  driver_voice_radar.html        # Sample embedded dashboard (demo)
assets/
  logo-passenger.png             # full Jeeny logo, pink - passenger brand
  logo-driver.png                # full Jeeny logo, purple - driver brand
  icon-passenger.png             # cropped glyph-only version (pink)
  icon-driver.png                # cropped glyph-only version (purple)
.streamlit/config.toml           # Jeeny pink theme
requirements.txt
```

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
`status_pill_html`, `stat_tile_html`, `issue_card_html`, `bar_html`) rather
than Streamlit's built-in `st.badge`/`st.metric`, whose fixed color palette
doesn't include Jeeny pink or purple. If you add a new HTML snippet like
these, always pass it through `styles.compact_html()` before concatenating it
with others - see the docstring on that function for why (a whitespace-only
line inside a raw-HTML block silently breaks Streamlit's Markdown rendering).

## Adding your real content

Everything you need to replace lives in `/data` and `/dashboard_files` — no
code changes required for routine updates.

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

If a dashboard is hosted externally (e.g. Power BI, Looker), you can instead
set `report_url` on the related study and/or extend the dashboard card to use
`st.link_button` to open it in a new tab.

### Add a new week

Append an entry to `data/weeks.json`:

```json
{ "id": "2026-w40", "label": "Week 40", "start_date": "2026-09-27", "end_date": "2026-10-03", "is_current": true }
```

Set `is_current` on the new week and unset it on the old one — Home and
Weekly Summary both default to whichever week has `is_current: true`, and
both also let the user pick any past week from the dropdown (the "weekly
filter" from the original brief).

### Log a cohort highlight

Append to `data/highlights.json`. `cohort` is one of `DX_KSA`, `DX_JOR`,
`PAX_KSA`, `PAX_JOR`. A bullet starting with `"Needs attention:"` is flagged
in pink on the Home page:

```json
{
  "week_id": "2026-w40",
  "cohort": "DX_KSA",
  "bullets": [
    "Summary bullet.",
    "Needs attention: something that needs follow-up."
  ]
}
```

### Log a survey, a WhatsApp/technical issue, or MSU/DIF fieldwork

- `data/surveys.json` — one object per survey per week (`sent`, `responses`,
  `dashboard_id` to link it to a dashboard on the Home page).
- `data/issues.json` — one object per manually-logged issue
  (`source`: `KSA`/`JO`, `category`: `Tech`/`Feedback`/`Fraud signal`,
  `status`: `New`/`Under review`/`Reported out`/`Closed`). Set
  `reference_type` (`"driver"` or `"passenger"`) and `reference_id` to a
  **masked internal case code** (e.g. `DRV-KSA-88213`) when the issue traces
  back to one person — never a phone number or other real identifier, per
  the Privacy section below.
- `data/msu_dif_performance.json` — `rows` (one per shopper/driver per week)
  plus `meta[week_id]` for the "X of 18 cities live on MSU survey" badge.

### Log social sentiment & app reviews

This section on Home is **empty until you add data** - `data/sentiment_summary.json`
and `data/sentiment_themes.json` both start as `[]`. Nothing is invented: no
rating, percentage, trend or theme is ever shown unless a real row backs it.

It's split into **two files on purpose**, so a week's total item volume can
never get silently confused with theme-mention volume (one review/post can
carry more than one theme tag, so theme mentions can legitimately sum to more
than the item count):

**`data/sentiment_summary.json`** — one object per (week, cohort, source_type).
`cohort` is one of `DX_KSA`, `DX_JOR`, `PAX_KSA`, `PAX_JOR`; `source_type` is
`"social_media"` or `"app_reviews"`. Only `week_id`, `cohort`, `source_type`,
`item_count`, `source` and `last_updated` are required - everything else is
optional and only renders when present:

```json
{
  "week_id": "2026-w39",
  "cohort": "DX_KSA",
  "source_type": "app_reviews",
  "item_count": 128,              // required - total reviews/posts collected this week
  "rating": 4.2,                  // optional - only shown for source_type "app_reviews"
  "rating_count": 128,             // optional - how many ratings the average covers
  "positive_count": 70,           // optional - all three must be present to show the mix bar
  "neutral_count": 40,            // optional
  "negative_count": 18,           // optional
  "source": "Google Play + App Store reviews",  // required - shown as-is under the card
  "last_updated": "2026-09-21"    // required - ISO date, shown as-is under the card
}
```

**`data/sentiment_themes.json`** — one object per (week, cohort, source_type,
theme), all four fields plus `mentions` required:

```json
{
  "week_id": "2026-w39",
  "cohort": "DX_KSA",
  "source_type": "app_reviews",
  "theme": "App stability",
  "mentions": 34
}
```

The Home page shows, per (cohort, source_type) combination you select:
summary cards built from whatever fields are present, a line chart of the
top 5 themes' mention counts for the 6 weeks ending at the selected week (or
fewer weeks, if `data/weeks.json` doesn't have 6 yet), and those themes'
change vs. the previous week. If neither file has a row for a given (week,
cohort, source_type), the panel shows "No sentiment data available for this
period" instead of guessing.

### Log completed fieldwork

`data/fieldwork.json` starts as `[]`. One object per completed piece of
fieldwork; `study`, `objective`, `market` and `week_id` are the fields the
table is built around, `completion_date` and `report_url` are optional
(a missing `report_url` just shows "—" instead of a link):

```json
{
  "id": "fw-2026-w39-01",
  "week_id": "2026-w39",
  "study": "Driver Voice Radar - Wave 3",
  "objective": "Track sentiment on earnings & app stability",
  "market": "KSA",
  "completion_date": "2026-09-24",
  "report_url": "https://your-dashboard-or-doc-link"   // optional
}
```

`week_id` should be the week the fieldwork **completed** in - the row shows
up on that week's Home page regardless of when the study started.

### Edit the Weekly Digest

Edit `data/weekly_digest.json` (one entry per `week_id`, with
`major_changes` and `recommended_areas`). This file is intentionally simple
JSON so it can later be generated automatically by a scheduled job.

Once you replace sample content with real data, set `"is_sample_data": false`
(or remove the field) so the "SAMPLE DATA" badges disappear.

## Privacy

- No passenger or driver phone numbers are shown anywhere in the app. Issues
  carry a masked internal case code instead (see above), never a phone
  number.
- Mask any personal identifiers before adding them to `data/*.json`.
- All data stays inside the app; nothing is sent to external services.
- The sidebar carries a persistent "Internal use only" label on every page.

## What's intentionally out of scope for v1

- User login / permissions
- Live Snowflake, SurveyMonkey, or Power BI connections
- AI-generated answers or a chatbot
- Action-management / task tracking

## Next version: connecting real automation

All data access is isolated in `modules/data_loader.py`. Page code (`Home.py`,
`views/*.py`) never reads files directly — it only calls functions like
`load_studies()`. That module already includes named placeholder functions
for the next integrations, so you can build them one at a time without
touching any page:

- `load_studies_from_snowflake()` — swap in a Snowflake query once
  `snowflake-connector-python` and credentials (via `st.secrets`) are set up.
  Have it return the same list-of-dict shape as `load_studies()` and it can
  replace the JSON read with no page changes.
- `load_responses_from_surveymonkey()` — pull raw survey responses via the
  SurveyMonkey API to auto-populate sample sizes and findings.
- `load_dashboard_metadata_from_powerbi()` — pull dashboard titles/refresh
  timestamps from the Power BI REST API to replace/augment `dashboards.json`.
- `load_studies_from_uploaded_csv()` — wire up an `st.file_uploader` (e.g. on
  a future internal "Admin" page) so studies can be added without editing
  JSON directly.
- `load_sentiment_from_snowflake()` — replace `_load_sentiment_summary_raw()`
  and `_load_sentiment_themes_raw()` with warehouse queries once your social
  listening / app review exports land in Snowflake. Keep the same two-file
  row shape (item counts separate from theme mentions) so `load_sentiment_summary()`,
  `load_theme_trend()` and `top_themes_with_delta()` - and the Home page code
  that calls them - don't need to change.
- `load_fieldwork_from_google_sheets()` — replace `_load_fieldwork_raw()`
  with a read from your team's shared fieldwork tracker sheet, mapped onto
  the same row shape as `data/fieldwork.json`. A short-TTL cache
  (`@st.cache_data(ttl=300)`) is recommended here since a Sheets API call is
  more expensive than reading a local file.
- `classify_text()` / `summarize_text()` — placeholders for future automated
  topic tagging and findings summarization (deliberately not implemented in
  v1, per project scope).

Because every page calls these functions instead of touching files directly,
swapping the data source is a backend change only — the UI, filters, and
navigation stay exactly the same.
