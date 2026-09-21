# Jeeny Insights Hub

A single place for the Market Intelligence team to find every study,
dashboard, weekly highlight and open issue - matching the Home /
Studies library / Dashboards flow from the wireframes.

## Stack

- **Backend:** Python (FastAPI), serving a small JSON REST API.
- **Frontend:** static HTML/CSS/vanilla JS (no build step) served by the
  same FastAPI app.
- **Data:** mock JSON files under `backend/app/data/` (one file per
  entity: weeks, studies, dashboards, highlights, surveys, issues,
  MSU/DIF performance). This is an MVP data source - swap
  `backend/app/data_store.py` for a real database or warehouse query
  layer later without touching the API routes or the frontend.

## Running locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --app-dir . --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

## Pages

- **Home (`/`)** - week picker (persisted per-browser), stat cards
  (Studies / Dashboards / Critical Issues), per-cohort highlights (DX
  KSA, DX JOR, PAX KSA, PAX JOR) with "needs attention" items called
  out, this week's survey completion, the manually-logged WhatsApp &
  technical issues feed (with driver/passenger reference IDs), and MSU
  & DIF fieldwork performance.
- **Studies library (`/studies`)** - every study, filterable by week,
  cohort and type, with search.
- **Dashboards (`/dashboards`)** - every live BI dashboard the team
  maintains, filterable by category, with search.

## API

All endpoints are read-only JSON under `/api`:

- `GET /api/weeks`
- `GET /api/weeks/{week_id}/summary` - stats, highlights, surveys,
  issues and MSU/DIF performance for one week (this is what the Home
  page renders).
- `GET /api/studies?week_id=&cohort=&type=&q=`
- `GET /api/studies/filters` - distinct weeks/cohorts/types for the
  Studies library filter bar.
- `GET /api/studies/{study_id}`
- `GET /api/dashboards?category=&q=`
- `GET /api/dashboards/{dashboard_id}`

## Updating content

Until a real backend is wired up, the team can add/edit content
directly in `backend/app/data/*.json`:

- Add a new week: append an entry to `weeks.json` (set `is_current` on
  the new one, unset it on the old one).
- Log a study: append to `studies.json` with the right `week_id` and
  `cohort` (`DX_KSA`, `DX_JOR`, `PAX_KSA`, `PAX_JOR`).
- Log a highlight: append to `highlights.json` (bullets starting with
  "Needs attention:" are visually flagged on the Home page).
- Log a WhatsApp/technical issue: append to `issues.json`, including
  `reference_type`/`reference_id` (driver or passenger ID) when the
  issue traces back to one person.
- Update MSU/DIF fieldwork: append to `performance.json` under `rows`,
  and update `meta[week_id]` for the "X of 18 cities live" badge.
