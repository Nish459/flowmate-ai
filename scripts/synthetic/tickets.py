"""Synthetic `tickets` table generation.

Non-Bug work item types use a generic state distribution. Bug tickets get
their own distribution (see patterns.BUG_STATE_WEIGHTS_*) because two of the
three engineered bottleneck patterns only apply to Bugs.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from faker import Faker

from . import patterns
from .entities import Sprint, Team, all_engineers, engineer_team, sprint_for_date

WORK_ITEM_TYPES = ["Task", "Bug", "User Story", "Feature", "Epic"]
WORK_ITEM_WEIGHTS = [0.40, 0.30, 0.20, 0.08, 0.02]

# Generic (non-Bug) state distribution.
STATE_WEIGHTS = {
    "New": 0.10, "Active": 0.28, "In Review": 0.17,
    "Blocked": 0.05, "Resolved": 0.18, "Closed": 0.22,
}

SEVERITIES = ["Critical", "High", "Medium", "Low"]
SEVERITY_WEIGHTS = [0.05, 0.20, 0.45, 0.30]

TAG_POOL = [
    "tech-debt", "customer-reported", "regression", "perf", "security",
    "flaky-test", "onboarding", "api", "ui-polish", "migration", "database",
]
BLOCKED_REASONS = [
    "Waiting on external API vendor",
    "Blocked by unresolved dependency ticket",
    "Waiting on design sign-off",
    "Environment/infra unavailable",
    "Waiting on customer clarification",
    "Blocked by failing CI pipeline",
]

_TERMINAL_STATES = {"Resolved", "Closed"}
_OPEN_STATES = {"New", "Active", "In Review", "Blocked"}


def _weighted_choice(rng: np.random.Generator, weights: dict[str, float]) -> str:
    options = list(weights.keys())
    probs = list(weights.values())
    return rng.choice(options, p=probs)


def _pick_work_item_type(rng: np.random.Generator, team_name: str) -> str:
    if team_name == patterns.SLOW_TEAM:
        others = [t for t in WORK_ITEM_TYPES if t != patterns.SLOW_TEAM_TICKET_TYPE]
        remaining = 1 - patterns.SLOW_TEAM_BUG_TYPE_WEIGHT
        base_weight_sum = sum(w for t, w in zip(WORK_ITEM_TYPES, WORK_ITEM_WEIGHTS) if t != patterns.SLOW_TEAM_TICKET_TYPE)
        weights = {patterns.SLOW_TEAM_TICKET_TYPE: patterns.SLOW_TEAM_BUG_TYPE_WEIGHT}
        for t, w in zip(WORK_ITEM_TYPES, WORK_ITEM_WEIGHTS):
            if t != patterns.SLOW_TEAM_TICKET_TYPE:
                weights[t] = remaining * (w / base_weight_sum)
        return _weighted_choice(rng, weights)
    return _weighted_choice(rng, dict(zip(WORK_ITEM_TYPES, WORK_ITEM_WEIGHTS)))


def _pick_tags(rng: np.random.Generator, team_name: str, work_item_type: str) -> tuple[str | None, bool]:
    is_slow_candidate = team_name == patterns.SLOW_TEAM and work_item_type == patterns.SLOW_TEAM_TICKET_TYPE
    tag_pool = list(TAG_POOL)
    n_tags = int(rng.integers(0, 3))
    chosen = list(rng.choice(tag_pool, size=n_tags, replace=False)) if n_tags else []

    inclusion_prob = patterns.SLOW_TEAM_TAG_INCLUSION_PROB if is_slow_candidate else patterns.BASELINE_TAG_INCLUSION_PROB
    matches_pattern = False
    if is_slow_candidate and rng.random() < inclusion_prob:
        forced_tag = rng.choice(list(patterns.SLOW_TEAM_TAGS))
        if forced_tag not in chosen:
            chosen.append(forced_tag)
        matches_pattern = True
    elif set(chosen) & patterns.SLOW_TEAM_TAGS and is_slow_candidate:
        matches_pattern = True

    return (", ".join(chosen) if chosen else None), matches_pattern


def _pick_state_weights(work_item_type: str, is_slow_pattern: bool, is_recent_window: bool) -> dict[str, float]:
    if is_slow_pattern:
        return patterns.SLOW_TEAM_STATE_WEIGHTS
    if work_item_type == "Bug":
        return patterns.BUG_STATE_WEIGHTS_RECENT_WINDOW if is_recent_window else patterns.BUG_STATE_WEIGHTS_BASELINE
    return STATE_WEIGHTS


def _make_ticket(
    idx: int,
    fake: Faker,
    rng: np.random.Generator,
    teams: list[Team],
    sprints: list[Sprint],
    now,
) -> dict:
    team = rng.choice(teams)
    team_name = team.name

    work_item_type = _pick_work_item_type(rng, team_name)
    tags, is_slow_pattern = _pick_tags(rng, team_name, work_item_type)

    horizon_start = sprints[0].start_date
    total_span_seconds = (now - horizon_start).total_seconds()
    created_date = horizon_start + timedelta(seconds=float(rng.uniform(0, total_span_seconds)))
    sprint = sprint_for_date(sprints, created_date)
    is_recent_window = sprint.sequence_number > (len(sprints) - patterns.RECENT_SPRINT_WINDOW)

    age_days = max((now - created_date).days, 1)
    state_weights = _pick_state_weights(work_item_type, is_slow_pattern, is_recent_window)
    state = _weighted_choice(rng, state_weights)

    cycle_multiplier = patterns.SLOW_TEAM_CYCLE_TIME_MULTIPLIER if is_slow_pattern else 1.0

    if state in _TERMINAL_STATES:
        if is_slow_pattern:
            # Bias closure toward the far end of the ticket's lifetime rather
            # than multiplying-then-capping at age_days, which would mask the
            # slow-team effect for tickets created recently.
            closed_offset_days = age_days - int(rng.uniform(0, age_days) / cycle_multiplier)
        else:
            closed_offset_days = int(rng.uniform(0, age_days))
        closed_offset_days = max(0, min(closed_offset_days, age_days))
        closed_date = created_date + timedelta(days=closed_offset_days)
        changed_date = closed_date
    else:
        closed_date = None
        is_stale = rng.random() < 0.18 or is_slow_pattern
        stale_low = min(7, age_days)
        if is_stale:
            days_since_change = int(rng.uniform(stale_low, max(stale_low, min(30, age_days))) * cycle_multiplier)
            days_since_change = min(days_since_change, age_days)
        else:
            days_since_change = int(rng.uniform(0, min(3, age_days)))
        changed_date = now - timedelta(days=days_since_change)
        if changed_date < created_date:
            changed_date = created_date

    state_entered_date = created_date + timedelta(
        seconds=float(rng.uniform(0, max((changed_date - created_date).total_seconds(), 1)))
    )

    priority = int(rng.choice([1, 2, 3, 4], p=[0.10, 0.30, 0.40, 0.20]))
    severity = _weighted_choice(rng, dict(zip(SEVERITIES, SEVERITY_WEIGHTS))) if work_item_type == "Bug" else None

    assigned_to = rng.choice(team.engineers) if state != "New" or rng.random() > 0.3 else None
    created_by = rng.choice(team.engineers)

    story_points = None
    if work_item_type in ("Task", "User Story", "Feature"):
        story_points = float(rng.choice([1, 2, 3, 5, 8, 13], p=[0.15, 0.25, 0.25, 0.20, 0.10, 0.05]))

    is_blocked = state == "Blocked" or (state == "Active" and rng.random() < (0.20 if is_slow_pattern else 0.10))
    blocked_reason = rng.choice(BLOCKED_REASONS) if is_blocked else None

    comment_count = int(rng.poisson(2.5))
    last_comment_date = None
    if comment_count > 0:
        last_comment_date = changed_date - timedelta(hours=float(rng.uniform(0, 48)))
        if last_comment_date < created_date:
            last_comment_date = created_date

    return {
        "ticket_id": f"TFS-{10000 + idx}",
        "title": fake.sentence(nb_words=6).rstrip("."),
        "description": fake.paragraph(nb_sentences=3),
        "work_item_type": work_item_type,
        "state": state,
        "priority": priority,
        "severity": severity,
        "team": team_name,
        "sprint_id": sprint.sprint_id,
        "assigned_to": assigned_to,
        "created_by": created_by,
        "created_date": created_date,
        "changed_date": changed_date,
        "state_entered_date": state_entered_date,
        "closed_date": closed_date,
        "area_path": f"FlowMate\\{team_name}",
        "iteration_path": f"FlowMate\\{sprint.sprint_id}",
        "story_points": story_points,
        "tags": tags,
        "depends_on_ticket_id": None,  # filled in by _assign_dependencies
        "is_blocked": bool(is_blocked),
        "blocked_reason": blocked_reason,
        "comment_count": comment_count,
        "last_comment_date": last_comment_date,
    }


def _assign_dependencies(df: pd.DataFrame, rng: np.random.Generator, prob: float = 0.12) -> pd.Series:
    """~`prob` of tickets depend on an earlier (by created_date) ticket."""
    ordered = df.sort_values("created_date")
    ordered_ids = ordered["ticket_id"].tolist()
    depends_on = {}
    for i in range(1, len(ordered_ids)):
        if rng.random() < prob:
            j = int(rng.integers(0, i))
            depends_on[ordered_ids[i]] = ordered_ids[j]
    return df["ticket_id"].map(depends_on)


def generate_tickets(
    num_tickets: int,
    rng: np.random.Generator,
    fake: Faker,
    teams: list[Team],
    sprints: list[Sprint],
    now,
) -> pd.DataFrame:
    rows = [_make_ticket(i, fake, rng, teams, sprints, now) for i in range(num_tickets)]
    df = pd.DataFrame(rows)

    df["depends_on_ticket_id"] = _assign_dependencies(df, rng)
    blocking_counts = df["depends_on_ticket_id"].value_counts()
    df["blocking_ticket_count"] = df["ticket_id"].map(blocking_counts).fillna(0).astype(int)

    timestamp_cols = ["created_date", "changed_date", "state_entered_date", "closed_date", "last_comment_date"]
    for col in timestamp_cols:
        df[col] = pd.to_datetime(df[col], utc=True)

    return df
