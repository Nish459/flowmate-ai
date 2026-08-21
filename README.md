# FlowMate

Multi-agent AI developer workflow assistant, built for the Patchamomma 2026
hackathon (deadline 2026-09-07).

Four agents (Google ADK + Gemini) read from a shared BigQuery ticket store
and reason about developer workflow health:

- **Ticket Watcher** — tracks ticket state changes
- **Review Nudger** — flags PRs/reviews stuck waiting on a reviewer
- **Standup Writer** — summarizes what each engineer did / is doing
- **Bottleneck Detector** — surfaces tickets stuck too long in one state

Stack: Python + FastAPI + Cloud Run + Firestore + React. GCP project:
`flowmate-ai-506118`. Model: `gemini-3.6-flash`.

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # fill in GEMINI_API_KEY

gcloud auth application-default login   # so the BigQuery client can authenticate
```

## Synthetic ticket data

Generate synthetic TFS-style work items and load them into BigQuery:

```bash
python scripts/generate_synthetic_tickets.py --num-tickets 800
python scripts/load_tickets_to_bigquery.py --truncate
```

This creates the `flowmate.tickets` BigQuery table (dataset auto-created if
missing). The schema is denormalized on purpose — one row per ticket with
enough signal (state, timestamps, review status, blocked flags) for all four
agents to query without joins. See `scripts/generate_synthetic_tickets.py`
for field-by-field rationale.

## Project layout

```
config/     shared settings (env-driven, single source of truth)
scripts/    one-off / operational scripts (data gen, BQ load, smoke tests)
data/       generated artifacts (gitignored — reproducible from scripts/)
```
