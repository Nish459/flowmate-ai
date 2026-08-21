"""If a column is added/renamed/removed in the generator but the loader's
BigQuery schema isn't updated to match, `load_synthetic_to_bigquery.py`
would fail at load time (or silently drop a column). Catch that here
instead, without needing real BigQuery access.
"""

import load_synthetic_to_bigquery as loader


def test_tickets_schema_matches_generated_columns(small_tickets_df):
    # small_tickets_df comes from generate_dataset(), which merges in
    # pull_request_id (derived from pr_reviews) before returning -- so it's
    # already present here, same as what actually gets written to parquet.
    schema_fields = {f.name for f in loader.TICKETS_SCHEMA}
    assert schema_fields == set(small_tickets_df.columns)


def test_pr_reviews_schema_matches_generated_columns(small_pr_reviews_df):
    schema_fields = {f.name for f in loader.PR_REVIEWS_SCHEMA}
    assert schema_fields == set(small_pr_reviews_df.columns)


def test_team_velocity_schema_matches_generated_columns(small_team_velocity_df):
    schema_fields = {f.name for f in loader.TEAM_VELOCITY_SCHEMA}
    assert schema_fields == set(small_team_velocity_df.columns)
