"""Referential-integrity checks run before writing the synthetic tables.

These catch dataset bugs cheaply and immediately, rather than surfacing as
confusing broken joins in a later BigQuery query or agent tool call.
"""

from __future__ import annotations

import pandas as pd


def validate(tickets_df: pd.DataFrame, pr_reviews_df: pd.DataFrame, team_velocity_df: pd.DataFrame, sprint_ids: set[str]) -> None:
    ticket_ids = set(tickets_df["ticket_id"])

    orphan_prs = set(pr_reviews_df["ticket_id"]) - ticket_ids
    assert not orphan_prs, f"pr_reviews reference unknown ticket_ids: {orphan_prs}"

    bad_ticket_sprints = set(tickets_df["sprint_id"]) - sprint_ids
    assert not bad_ticket_sprints, f"tickets reference unknown sprint_ids: {bad_ticket_sprints}"

    bad_pr_sprints = set(pr_reviews_df["sprint_id"]) - sprint_ids
    assert not bad_pr_sprints, f"pr_reviews reference unknown sprint_ids: {bad_pr_sprints}"

    expected_velocity_rows = tickets_df["team"].nunique() * len(sprint_ids)
    assert len(team_velocity_df) == expected_velocity_rows, (
        f"team_velocity should have exactly teams x sprints rows: "
        f"expected {expected_velocity_rows}, got {len(team_velocity_df)}"
    )
    assert not team_velocity_df.duplicated(subset=["team", "sprint_id"]).any(), "duplicate (team, sprint_id) rows"

    created_by_id = tickets_df.set_index("ticket_id")["created_date"]
    deps = tickets_df.dropna(subset=["depends_on_ticket_id"])
    for ticket_id, dep_id in zip(deps["ticket_id"], deps["depends_on_ticket_id"]):
        assert created_by_id[dep_id] < created_by_id[ticket_id], (
            f"{ticket_id} depends on {dep_id}, which was created later"
        )

    print("Validation passed: referential integrity checks OK.")
