# FlowMate

Multi-agent AI developer workflow assistant, built for the Patchamomma 2026
hackathon (deadline 2026-09-07).

Four agents (Google ADK + Gemini) read from BigQuery and reason about
developer workflow health:

- **Ticket Watcher** — tracks ticket state changes, flags blocked items / missing assignees
- **Review Nudger** — flags PRs stuck without review, drafts follow-ups
- **Standup Writer** — summarizes what each engineer did / is doing / is blocked on
- **Bottleneck Detector** — reasons across sprint history to flag tickets at risk of missing deadline

The orchestrator (`agents/orchestrator`) runs Ticket Watcher + Bottleneck
Detector in parallel, then feeds their output into Review Nudger + Standup
Writer, matching the project architecture.

Stack: Python + FastAPI + Cloud Run + Firestore + React. GCP project:
`flowmate-ai-506118`. Model: `gemini-3.6-flash`.

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # fill in GEMINI_API_KEY

gcloud auth application-default login   # so the BigQuery client can authenticate
```

## Synthetic dataset

Generate three synthetic, BigQuery-shaped tables and load them:

```bash
python scripts/generate_synthetic_dataset.py --num-tickets 800
python scripts/load_synthetic_to_bigquery.py --truncate
```

This creates `flowmate.{tickets, pr_reviews, team_velocity}` (dataset
auto-created if missing). The three tables share teams/sprints as join keys
(`team`, `sprint_id`, `ticket_id`) and carry deliberately engineered
patterns — not random noise — so the Bottleneck Detector agent has real
signal to find:

- **DevOps** is slow on **Bug** tickets tagged `migration`/`database`
- One specific reviewer has much higher review latency and a higher changes-requested rate
- **Bug** tickets created in the most recent sprints have a depressed close rate

See `scripts/synthetic/patterns.py` for exact parameters and rationale.

## Agents (skeleton)

```
agents/
  common/bigquery_tool.py     shared read-only BQ tool, used by all 4 agents
  ticket_watcher/agent.py
  review_nudger/agent.py
  standup_writer/agent.py
  bottleneck_detector/agent.py
  orchestrator/agent.py       wires the fan-out/fan-in shape above
```

Each agent is currently a stub (real reasoning logic lands per the project
timeline) but is wired to real tools and real BigQuery data. Exercise it with
ADK's own CLI:

```bash
export GOOGLE_API_KEY="$(grep GEMINI_API_KEY .env | cut -d= -f2)"
adk run agents/orchestrator   # or: adk web
```

## Project layout

```
config/     shared settings (env-driven, single source of truth)
scripts/    one-off / operational scripts (data gen, BQ load, smoke tests)
  synthetic/  the 3-table generator package (entities, patterns, per-table builders)
agents/     Google ADK agent skeleton
data/       generated artifacts (gitignored — reproducible from scripts/)
```
