# FlowMate

Multi-agent AI developer workflow assistant, built solo for the Patchamomma 2026 hackathon
(deadline 2026-09-07).

**Live demo:**
- Dashboard: https://flowmate-ai-506118.web.app
- API: https://flowmate-api-777747272707.us-central1.run.app

Engineering teams lose time to coordination overhead — chasing reviewers, digging through tickets
to find what's actually blocked, writing standups, discovering at-risk sprint items too late.
FlowMate automates this with four Google ADK + Gemini agents sitting on top of ticket/PR/velocity
data, surfaced through a React dashboard and a manager-facing Looker Studio view.

## The four agents

Each reads real BigQuery data via shared, read-only SQL tools (`agents/common/bigquery_tool.py`) and
reasons over it with Gemini — no rule-based alerting.

- **Ticket Watcher** — flags tickets that are stale (24h+ untouched), blocked, or missing an
  assignee. Reports full totals per category plus a capped, prioritized detail list (so nothing is
  hidden, but output stays scannable).
- **Review Nudger** — finds PRs sitting without review, drafts a follow-up message that references
  the *real* sprint end date, not a generic ping.
- **Standup Writer** — writes each engineer's done/doing/blocked/next update. Also maintains a
  Firestore-cached daily history per engineer, browsable by date range in the dashboard.
- **Bottleneck Detector** — the centerpiece. Cross-references four independent signals (current
  open tickets, historical close rates by team × ticket type, reviewer latency, and bug close-rate
  trend) to flag tickets at high risk of missing the deadline, days before it happens.

The orchestrator (`agents/orchestrator`) runs Ticket Watcher + Bottleneck Detector in parallel, then
feeds into Review Nudger + Standup Writer.

## Architecture

```
React dashboard (Firebase Hosting)
        |
        v
FastAPI backend (Cloud Run)  ---->  ADK agents (Gemini) ---->  BigQuery (tickets, pr_reviews, team_velocity)
        |                                                              ^
        v                                                              |
   Firestore (cached scan output, cached table data, standup history)  |
                                                                        |
                                              Looker Studio (manager bottleneck heatmap) ---+
```

The dashboard never blocks on a live agent scan (~6.5 min for a full sequential run, due to the
Gemini free-tier's per-minute cap): `POST /scan` and `GET /panels` are the slow, live-BigQuery/Gemini
refresh paths; `GET /scan/latest` and `GET /panels/latest` serve the Firestore-cached result instantly
and are what the frontend actually reads on load.

## Tech stack

| Layer | Technology |
|---|---|
| AI reasoning | Gemini 3.6 Flash, via `google-genai` and Google ADK |
| Agent orchestration | Google ADK (`Agent`, `ParallelAgent`, `SequentialAgent`) |
| Data storage | BigQuery (tickets/PRs/velocity), Firestore (caches, standup history) |
| Backend | Python + FastAPI, containerized, deployed on Cloud Run |
| Dashboard | React + Vite, deployed on Firebase Hosting |
| Manager view | Looker Studio, connected directly to BigQuery views |
| Demo data | Synthetic, generated with Python + Faker + NumPy |

GCP project: `flowmate-ai-506118`. Model: `gemini-3.6-flash`.

## Running it locally

### Backend

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt   # requirements.txt + pytest

cp .env.example .env                  # fill in GEMINI_API_KEY
gcloud auth application-default login # so the BigQuery/Firestore clients can authenticate

export GOOGLE_API_KEY="$(grep GEMINI_API_KEY .env | cut -d= -f2)"
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, expects the API at http://localhost:8000
```

Set `VITE_API_BASE_URL` (see `frontend/.env.example`) to point at a different backend, e.g. the
deployed Cloud Run URL.

### Tests

```bash
pytest -q   # ~120 tests, all monkeypatched/mocked, no live network calls, runs in under a second
```

## Synthetic dataset

Generate three synthetic, BigQuery-shaped tables and load them:

```bash
python scripts/generate_synthetic_dataset.py --num-tickets 800 --seed 42
python scripts/load_synthetic_to_bigquery.py --truncate
bq query --project_id=flowmate-ai-506118 --use_legacy_sql=false < scripts/create_looker_views.sql
```

This creates `flowmate.{tickets, pr_reviews, team_velocity}` plus three Looker Studio-facing views.
The three base tables share teams/sprints as join keys (`team`, `sprint_id`, `ticket_id`) and carry
deliberately engineered patterns — not random noise — so the Bottleneck Detector agent and the Looker
Studio heatmap both have real signal to find:

- **DevOps** is slow on **Bug** tickets tagged `migration`/`database`
- One specific reviewer has much higher review latency and a higher changes-requested rate
- **Bug** tickets created in the most recent sprints have a depressed close rate

Ticket titles are generated from work-item-type- and tag-aware templates (not raw random sentences),
so they read as plausible engineering work — e.g. "Fix crash in database migration script" for a
Bug tagged `migration`. See `scripts/synthetic/patterns.py` for the exact engineered parameters and
rationale, and `scripts/synthetic/tickets.py` for the title templates.

## Deployment

```bash
# Backend -> Cloud Run (Secret Manager holds the Gemini key; see CLAUDE.md for the one-time setup)
gcloud run deploy flowmate-api --source . --project=flowmate-ai-506118 --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars=GCP_PROJECT_ID=flowmate-ai-506118 \
  --set-secrets=GOOGLE_API_KEY=gemini-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest

# Frontend -> Firebase Hosting
cd frontend && VITE_API_BASE_URL=<cloud-run-url> npm run build && cd ..
firebase deploy --only hosting --project flowmate-ai-506118
```

## Project layout

```
config/       shared settings (env-driven, single source of truth)
agents/       Google ADK agents + shared BigQuery/Firestore tools
  common/       bigquery_tool.py (shared read-only tools), firestore_client.py, agent_runner.py
  orchestrator/ fan-out/fan-in wiring
api/          FastAPI backend (Cloud Run)
frontend/     React + Vite dashboard (Firebase Hosting)
scripts/      one-off / operational scripts (data gen, BQ load, Looker views, smoke tests)
  synthetic/    the 3-table generator package (entities, patterns, per-table builders)
tests/        pytest suite — data generation, BigQuery tool, agents, API, Firestore client
data/         generated artifacts (gitignored — reproducible from scripts/)
Dockerfile    backend container image for Cloud Run
```

## Known limitations

- The Gemini Developer API key used here is on the **free tier**: 20 requests/day for
  `gemini-3.6-flash`. `POST /scan` runs its 4 agents sequentially (not concurrently) specifically to
  stay under the per-minute cap; the dashboard itself never triggers a live scan, only reads the
  cached result, so this doesn't affect normal use of the demo.
- Standup Writer's Phase 2 (a conversational "what did I do last week?" endpoint) is a stretch goal,
  not built — the underlying query functions are already parameterized for it.
