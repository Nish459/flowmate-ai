"""Synthetic `team_velocity` table generation.

Unlike `tickets` and `pr_reviews`, this table is entirely *derived* by
aggregating the already-generated `tickets` dataframe -- not independently
randomized -- so the two views can never contradict each other (e.g.
`team_velocity` can't show a team over-delivering while `tickets` shows most
of that team's work still open).
"""

from __future__ import annotations

import pandas as pd

from .entities import Sprint, Team


def generate_team_velocity(tickets_df: pd.DataFrame, teams: list[Team], sprints: list[Sprint]) -> pd.DataFrame:
    team_names = [t.name for t in teams]

    rows = []
    for team_name in team_names:
        for sprint in sprints:
            subset = tickets_df[(tickets_df["team"] == team_name) & (tickets_df["sprint_id"] == sprint.sprint_id)]

            committed_points = float(subset["story_points"].fillna(0).sum())
            delivered_points = float(
                subset.loc[subset["state"].isin(["Resolved", "Closed"]), "story_points"].fillna(0).sum()
            )
            blocker_count = int(subset["is_blocked"].sum())
            ticket_count = int(len(subset))
            miss_rate = 0.0 if committed_points == 0 else round(1 - (delivered_points / committed_points), 4)

            rows.append(
                {
                    "team": team_name,
                    "sprint_id": sprint.sprint_id,
                    "sprint_start_date": sprint.start_date,
                    "sprint_end_date": sprint.end_date,
                    "committed_points": committed_points,
                    "delivered_points": delivered_points,
                    "blocker_count": blocker_count,
                    "ticket_count": ticket_count,
                    "miss_rate": miss_rate,
                }
            )

    df = pd.DataFrame(rows)
    for col in ["sprint_start_date", "sprint_end_date"]:
        df[col] = pd.to_datetime(df[col], utc=True)
    return df
