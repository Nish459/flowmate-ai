"""Shared entities (teams, sprints) used across all three synthetic tables.

Generating these once and threading them through tickets -> pr_reviews ->
team_velocity is what keeps `team` and `sprint_id` valid join keys across
the three BigQuery tables instead of three independently-randomized tables
that happen to share column names.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from faker import Faker

SPRINT_LENGTH_DAYS = 14

TEAM_ROSTER_SIZES = {
    "Backend": 4,
    "Frontend": 3,
    "Data Platform": 3,
    "DevOps": 3,
    "Mobile": 3,
}


@dataclass(frozen=True)
class Team:
    name: str
    engineers: list[str]


@dataclass(frozen=True)
class Sprint:
    sprint_id: str
    sequence_number: int
    start_date: datetime
    end_date: datetime


def build_teams(fake: Faker) -> list[Team]:
    return [
        Team(name=team_name, engineers=[fake.unique.name() for _ in range(size)])
        for team_name, size in TEAM_ROSTER_SIZES.items()
    ]


def all_engineers(teams: list[Team]) -> list[str]:
    return [engineer for team in teams for engineer in team.engineers]


def engineer_team(teams: list[Team], engineer: str) -> str:
    for team in teams:
        if engineer in team.engineers:
            return team.name
    raise ValueError(f"Unknown engineer: {engineer}")


def build_sprints(now: datetime, horizon_days: int) -> list[Sprint]:
    """Generate biweekly sprints covering [now - horizon_days, now].

    At least 6 sprints even for a short horizon, so team_velocity always has
    enough history for a trend to be visible.
    """
    num_sprints = max(6, math.ceil(horizon_days / SPRINT_LENGTH_DAYS))
    horizon_start = now - timedelta(days=num_sprints * SPRINT_LENGTH_DAYS)

    sprints = []
    for seq in range(1, num_sprints + 1):
        start = horizon_start + timedelta(days=(seq - 1) * SPRINT_LENGTH_DAYS)
        end = start + timedelta(days=SPRINT_LENGTH_DAYS)
        sprints.append(
            Sprint(
                sprint_id=f"SPR-2026-{seq:02d}",
                sequence_number=seq,
                start_date=start,
                end_date=end,
            )
        )
    return sprints


def sprint_for_date(sprints: list[Sprint], when: datetime) -> Sprint:
    """Return the sprint containing `when`, clamping to the nearest edge sprint
    if `when` falls outside the generated sprint range (can happen for dates
    very close to `now`, after the last sprint's end)."""
    for sprint in sprints:
        if sprint.start_date <= when < sprint.end_date:
            return sprint
    return sprints[-1] if when >= sprints[-1].end_date else sprints[0]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
