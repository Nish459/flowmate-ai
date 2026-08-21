"""Statistical checks that the three deliberately-engineered bottleneck
patterns (see synthetic/patterns.py) actually show up in generated data.
These are the tests that matter most for the Bottleneck Detector milestone:
if one of these regresses, the demo's "predictive" story has nothing real
behind it.
"""

import pandas as pd

from synthetic import patterns


def _is_slow_team_pattern_ticket(row) -> bool:
    if row["team"] != patterns.SLOW_TEAM or row["work_item_type"] != patterns.SLOW_TEAM_TICKET_TYPE:
        return False
    raw_tags = row["tags"]
    if pd.isna(raw_tags):
        return False
    tags = {t.strip() for t in raw_tags.split(",") if t.strip()}
    return bool(tags & patterns.SLOW_TEAM_TAGS)


def test_slow_team_pattern_has_enough_rows_to_be_meaningful(small_tickets_df):
    mask = small_tickets_df.apply(_is_slow_team_pattern_ticket, axis=1)
    assert mask.sum() >= 10


def test_slow_team_pattern_reduces_close_rate(small_tickets_df):
    mask = small_tickets_df.apply(_is_slow_team_pattern_ticket, axis=1)
    slow_close_rate = small_tickets_df.loc[mask, "state"].isin(["Resolved", "Closed"]).mean()
    rest_close_rate = small_tickets_df.loc[~mask, "state"].isin(["Resolved", "Closed"]).mean()
    assert slow_close_rate < rest_close_rate


def test_slow_reviewer_pattern_creates_a_clear_latency_outlier(small_pr_reviews_df):
    reviewed = small_pr_reviews_df.dropna(subset=["review_latency_hours"])
    by_reviewer = reviewed.groupby("reviewer")["review_latency_hours"].mean().sort_values(ascending=False)
    assert len(by_reviewer) >= 3
    top = by_reviewer.iloc[0]
    median_of_rest = by_reviewer.iloc[1:].median()
    assert top > 2 * median_of_rest


def test_recent_sprint_window_depresses_bug_close_rate(small_tickets_df):
    sprints_sorted = sorted(small_tickets_df["sprint_id"].unique())
    recent = set(sprints_sorted[-patterns.RECENT_SPRINT_WINDOW :])
    bugs = small_tickets_df[small_tickets_df["work_item_type"] == "Bug"]
    recent_bugs = bugs[bugs["sprint_id"].isin(recent)]
    older_bugs = bugs[~bugs["sprint_id"].isin(recent)]
    assert len(recent_bugs) >= 5
    assert len(older_bugs) >= 5
    assert recent_bugs["state"].isin(["Resolved", "Closed"]).mean() < older_bugs["state"].isin(["Resolved", "Closed"]).mean()
