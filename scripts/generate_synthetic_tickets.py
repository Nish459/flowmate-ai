#!/usr/bin/env python3
"""Generate synthetic TFS-style work item (ticket) data for FlowMate.

The schema is deliberately denormalized and carries enough signal for all
four downstream agents without requiring a join at read time:

  - Ticket Watcher    -> state, work_item_type, created_date/changed_date
  - Review Nudger     -> reviewer, review_status, review_requested_date
  - Standup Writer    -> assigned_to, changed_date, state, comment_count
  - Bottleneck Detector -> state_entered_date, is_blocked, priority

Usage:
    python scripts/generate_synthetic_tickets.py --num-tickets 800 --seed 42
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

WORK_ITEM_TYPES = ["Task", "Bug", "User Story", "Feature", "Epic"]
WORK_ITEM_WEIGHTS = [0.40, 0.30, 0.20, 0.08, 0.02]

STATES = ["New", "Active", "In Review", "Blocked", "Resolved", "Closed"]
STATE_WEIGHTS = [0.10, 0.25, 0.15, 0.08, 0.20, 0.22]

SEVERITIES = ["Critical", "High", "Medium", "Low"]
SEVERITY_WEIGHTS = [0.05, 0.20, 0.45, 0.30]

REVIEW_STATUSES = ["Not Started", "Pending", "Approved", "Changes Requested"]
REVIEW_STATUS_WEIGHTS = [0.15, 0.45, 0.25, 0.15]

AREAS = ["Backend", "Frontend", "Data Platform", "DevOps", "Mobile", "QA"]
TAG_POOL = [
    "tech-debt", "customer-reported", "regression", "perf", "security",
    "flaky-test", "onboarding", "api", "ui-polish", "migration",
]
BLOCKED_REASONS = [
    "Waiting on external API vendor",
    "Blocked by unresolved dependency ticket",
    "Waiting on design sign-off",
    "Environment/infra unavailable",
    "Waiting on customer clarification",
    "Blocked by failing CI pipeline",
]

_OPEN_STATES = {"New", "Active", "In Review", "Blocked"}
_TERMINAL_STATES = {"Resolved", "Closed"}


@dataclass(frozen=True)
class Team:
    engineers: list[str]
    reviewers: list[str]


def _build_team(fake: Faker, size: int = 12) -> Team:
    names = [fake.unique.name() for _ in range(size)]
    return Team(engineers=names, reviewers=names)


def _weighted_choice(rng: np.random.Generator, options: list[str], weights: list[float]) -> str:
    return rng.choice(options, p=weights)


def _gen_iteration_path(sprint_number: int) -> str:
    return f"FlowMate\\Sprint {sprint_number}"


def _make_ticket(
    idx: int,
    fake: Faker,
    rng: np.random.Generator,
    team: Team,
    now: datetime,
    horizon_days: int,
) -> dict:
    work_item_type = _weighted_choice(rng, WORK_ITEM_TYPES, WORK_ITEM_WEIGHTS)
    state = _weighted_choice(rng, STATES, STATE_WEIGHTS)

    created_offset_days = int(rng.uniform(1, horizon_days))
    created_date = now - timedelta(
        days=created_offset_days,
        hours=int(rng.uniform(0, 23)),
        minutes=int(rng.uniform(0, 59)),
    )

    # Time the ticket has spent alive so far, used to derive changed/closed dates.
    age_days = max((now - created_date).days, 1)

    if state in _TERMINAL_STATES:
        closed_offset_days = int(rng.uniform(0, age_days))
        closed_date = created_date + timedelta(days=closed_offset_days)
        changed_date = closed_date
    else:
        closed_date = None
        # Most open tickets were touched recently; a "stale" tail feeds the
        # Bottleneck Detector with tickets that have gone quiet.
        is_stale = rng.random() < 0.18
        stale_low = min(7, age_days)
        if is_stale:
            days_since_change = int(rng.uniform(stale_low, max(stale_low, min(30, age_days))))
        else:
            days_since_change = int(rng.uniform(0, min(3, age_days)))
        changed_date = now - timedelta(days=days_since_change)
        if changed_date < created_date:
            changed_date = created_date

    # When the ticket entered its *current* state — always between created_date
    # and changed_date. This is what Bottleneck Detector uses for time-in-state.
    state_entered_date = created_date + timedelta(
        seconds=int(rng.uniform(0, max((changed_date - created_date).total_seconds(), 1)))
    )

    priority = int(rng.choice([1, 2, 3, 4], p=[0.10, 0.30, 0.40, 0.20]))
    severity = _weighted_choice(rng, SEVERITIES, SEVERITY_WEIGHTS) if work_item_type == "Bug" else None

    assigned_to = rng.choice(team.engineers) if state != "New" or rng.random() > 0.3 else None
    created_by = rng.choice(team.engineers)

    story_points = None
    if work_item_type in ("Task", "User Story", "Feature"):
        story_points = float(rng.choice([1, 2, 3, 5, 8, 13], p=[0.15, 0.25, 0.25, 0.20, 0.10, 0.05]))

    tags = ", ".join(rng.choice(TAG_POOL, size=int(rng.integers(0, 3)), replace=False))

    reviewer = review_status = review_requested_date = pull_request_id = None
    if state == "In Review":
        reviewer = rng.choice(team.reviewers)
        review_status = _weighted_choice(rng, REVIEW_STATUSES, REVIEW_STATUS_WEIGHTS)
        review_wait_days = int(rng.uniform(0, 6))
        review_requested_date = changed_date - timedelta(days=max(review_wait_days - 1, 0))
        pull_request_id = f"PR-{fake.unique.random_int(min=1000, max=99999)}"

    is_blocked = state == "Blocked" or (state == "Active" and rng.random() < 0.10)
    blocked_reason = rng.choice(BLOCKED_REASONS) if is_blocked else None

    comment_count = int(rng.poisson(2.5))
    last_comment_date = None
    if comment_count > 0:
        last_comment_date = changed_date - timedelta(hours=int(rng.uniform(0, 48)))
        if last_comment_date < created_date:
            last_comment_date = created_date

    sprint_number = max(1, 20 - created_offset_days // 14)

    return {
        "ticket_id": f"TFS-{10000 + idx}",
        "title": fake.sentence(nb_words=6).rstrip("."),
        "description": fake.paragraph(nb_sentences=3),
        "work_item_type": work_item_type,
        "state": state,
        "priority": priority,
        "severity": severity,
        "assigned_to": assigned_to,
        "created_by": created_by,
        "created_date": created_date,
        "changed_date": changed_date,
        "state_entered_date": state_entered_date,
        "closed_date": closed_date,
        "area_path": f"FlowMate\\{rng.choice(AREAS)}",
        "iteration_path": _gen_iteration_path(sprint_number),
        "story_points": story_points,
        "tags": tags or None,
        "reviewer": reviewer,
        "review_status": review_status,
        "review_requested_date": review_requested_date,
        "pull_request_id": pull_request_id,
        "is_blocked": bool(is_blocked),
        "blocked_reason": blocked_reason,
        "comment_count": comment_count,
        "last_comment_date": last_comment_date,
    }


def generate_tickets(num_tickets: int, seed: int, horizon_days: int) -> pd.DataFrame:
    random.seed(seed)
    rng = np.random.default_rng(seed)
    fake = Faker()
    Faker.seed(seed)

    team = _build_team(fake)
    now = datetime.now(timezone.utc)

    rows = [_make_ticket(i, fake, rng, team, now, horizon_days) for i in range(num_tickets)]
    df = pd.DataFrame(rows)

    timestamp_cols = [
        "created_date", "changed_date", "state_entered_date",
        "closed_date", "review_requested_date", "last_comment_date",
    ]
    for col in timestamp_cols:
        df[col] = pd.to_datetime(df[col], utc=True)

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-tickets", type=int, default=800)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--horizon-days", type=int, default=90, help="How far back tickets can be created.")
    parser.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "synthetic" / "tickets.parquet",
    )
    args = parser.parse_args()

    df = generate_tickets(args.num_tickets, args.seed, args.horizon_days)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"Generated {len(df)} synthetic tickets -> {args.out}")
    print(df["state"].value_counts())


if __name__ == "__main__":
    main()
