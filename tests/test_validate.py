import pandas as pd
import pytest

from synthetic import validate as validate_mod


def _sprint_ids(tickets_df, team_velocity_df):
    return set(tickets_df["sprint_id"]) | set(team_velocity_df["sprint_id"])


def test_validate_passes_on_a_correctly_generated_dataset(small_tickets_df, small_pr_reviews_df, small_team_velocity_df):
    validate_mod.validate(
        small_tickets_df, small_pr_reviews_df, small_team_velocity_df, _sprint_ids(small_tickets_df, small_team_velocity_df)
    )


def test_validate_catches_orphan_pr_review(small_tickets_df, small_pr_reviews_df, small_team_velocity_df):
    broken = small_pr_reviews_df.copy()
    broken.loc[broken.index[0], "ticket_id"] = "TFS-99999999"
    with pytest.raises(AssertionError):
        validate_mod.validate(small_tickets_df, broken, small_team_velocity_df, _sprint_ids(small_tickets_df, small_team_velocity_df))


def test_validate_catches_unknown_sprint_id(small_tickets_df, small_pr_reviews_df, small_team_velocity_df):
    broken = small_tickets_df.copy()
    broken.loc[broken.index[0], "sprint_id"] = "SPR-9999-99"
    with pytest.raises(AssertionError):
        validate_mod.validate(broken, small_pr_reviews_df, small_team_velocity_df, _sprint_ids(small_tickets_df, small_team_velocity_df))


def test_validate_catches_duplicate_team_velocity_row(small_tickets_df, small_pr_reviews_df, small_team_velocity_df):
    broken = pd.concat([small_team_velocity_df, small_team_velocity_df.iloc[[0]]], ignore_index=True)
    with pytest.raises(AssertionError):
        validate_mod.validate(small_tickets_df, small_pr_reviews_df, broken, _sprint_ids(small_tickets_df, small_team_velocity_df))


def test_validate_catches_forward_pointing_dependency(small_tickets_df, small_pr_reviews_df, small_team_velocity_df):
    broken = small_tickets_df.copy()
    with_dep = broken.dropna(subset=["depends_on_ticket_id"])
    assert len(with_dep) > 0
    row_idx = with_dep.index[0]
    dep_id = broken.loc[row_idx, "depends_on_ticket_id"]
    # Force the dependency to point at a ticket created *after* it.
    broken.loc[broken["ticket_id"] == dep_id, "created_date"] = broken["created_date"].max()
    broken.loc[row_idx, "created_date"] = broken["created_date"].min()
    with pytest.raises(AssertionError):
        validate_mod.validate(broken, small_pr_reviews_df, small_team_velocity_df, _sprint_ids(small_tickets_df, small_team_velocity_df))
