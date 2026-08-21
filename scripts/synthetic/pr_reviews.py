"""Synthetic `pr_reviews` table generation.

Generated from the already-built `tickets` dataframe: only tickets that
reached "In Review" or a terminal state, and whose type typically carries a
PR, get a review row. One PR per eligible ticket (simplification -- real
TFS/DevOps data can have re-opened PRs, but one-per-ticket is enough signal
for the Bottleneck/Review Nudger agents this dataset feeds).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from faker import Faker

from . import patterns
from .entities import Team, all_engineers

_ELIGIBLE_STATES = {"In Review", "Resolved", "Closed"}
_ELIGIBLE_TYPES = {"Task", "Bug", "User Story", "Feature"}  # Epics don't get direct PRs
_PR_COVERAGE = 0.60  # fraction of eligible tickets that get a PR row


def _slow_reviewer(teams: list[Team]) -> str:
    engineers = sorted(all_engineers(teams))
    return engineers[patterns.SLOW_REVIEWER_INDEX]


def _pick_reviewer(rng: np.random.Generator, engineers: list[str], author: str, slow_reviewer: str) -> str:
    candidates = [e for e in engineers if e != author]
    # Slight bias so the slow reviewer gets a healthy, but not overwhelming,
    # share of reviews -- enough rows for the pattern to be statistically visible.
    if slow_reviewer in candidates and rng.random() < 0.25:
        return slow_reviewer
    return rng.choice(candidates)


def _make_pr_row(
    ticket: pd.Series,
    fake: Faker,
    rng: np.random.Generator,
    engineers: list[str],
    slow_reviewer: str,
    now,
) -> dict:
    author = ticket["assigned_to"] or ticket["created_by"]
    reviewer = _pick_reviewer(rng, engineers, author, slow_reviewer)
    is_slow_reviewer = reviewer == slow_reviewer

    pr_created = ticket["state_entered_date"] if ticket["state"] == "In Review" else ticket["changed_date"] - timedelta(
        hours=float(rng.uniform(1, 48))
    )
    if pr_created < ticket["created_date"]:
        pr_created = ticket["created_date"]
    review_requested_date = pr_created + timedelta(hours=float(rng.uniform(0, 4)))

    pending_prob = 0.25 if is_slow_reviewer else 0.15
    is_pending = ticket["state"] == "In Review" and rng.random() < pending_prob

    reviewed_date = None
    review_status = "Pending"
    latency_hours = None
    if not is_pending:
        mean_h = patterns.SLOW_REVIEWER_LATENCY_MEAN_HOURS if is_slow_reviewer else patterns.BASELINE_REVIEW_LATENCY_MEAN_HOURS
        sigma = patterns.SLOW_REVIEWER_LATENCY_SIGMA if is_slow_reviewer else patterns.BASELINE_REVIEW_LATENCY_SIGMA
        latency_hours = float(rng.lognormal(mean=np.log(mean_h), sigma=sigma))
        reviewed_date = review_requested_date + timedelta(hours=latency_hours)
        if reviewed_date > now:
            reviewed_date = now
            latency_hours = (reviewed_date - review_requested_date).total_seconds() / 3600

        changes_requested_rate = (
            patterns.SLOW_REVIEWER_CHANGES_REQUESTED_RATE if is_slow_reviewer else patterns.BASELINE_CHANGES_REQUESTED_RATE
        )
        review_status = "Changes Requested" if rng.random() < changes_requested_rate else "Approved"

    lines_added = int(rng.poisson(60) + 1)
    lines_removed = int(rng.poisson(25))

    return {
        "pr_id": f"PR-{fake.unique.random_int(min=1000, max=999999)}",
        "ticket_id": ticket["ticket_id"],
        "author": author,
        "reviewer": reviewer,
        "team": ticket["team"],
        "sprint_id": ticket["sprint_id"],
        "created_date": pr_created,
        "review_requested_date": review_requested_date,
        "reviewed_date": reviewed_date,
        "review_status": review_status,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "lines_changed": lines_added + lines_removed,
        "review_latency_hours": latency_hours,
    }


def generate_pr_reviews(
    tickets_df: pd.DataFrame,
    rng: np.random.Generator,
    fake: Faker,
    teams: list[Team],
    now,
) -> pd.DataFrame:
    engineers = all_engineers(teams)
    slow_reviewer = _slow_reviewer(teams)

    eligible = tickets_df[
        tickets_df["state"].isin(_ELIGIBLE_STATES) & tickets_df["work_item_type"].isin(_ELIGIBLE_TYPES)
    ]
    coverage_mask = rng.random(len(eligible)) < _PR_COVERAGE
    selected = eligible[coverage_mask]

    rows = [_make_pr_row(ticket, fake, rng, engineers, slow_reviewer, now) for _, ticket in selected.iterrows()]
    df = pd.DataFrame(rows)

    timestamp_cols = ["created_date", "review_requested_date", "reviewed_date"]
    for col in timestamp_cols:
        df[col] = pd.to_datetime(df[col], utc=True)

    return df
