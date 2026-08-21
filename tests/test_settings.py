from config.settings import Settings


def test_table_id_properties_compose_project_dataset_table():
    s = Settings(
        _env_file=None,
        GCP_PROJECT_ID="proj",
        BQ_DATASET="ds",
        BQ_TICKETS_TABLE="t",
        BQ_PR_REVIEWS_TABLE="p",
        BQ_TEAM_VELOCITY_TABLE="v",
    )
    assert s.bq_tickets_table_id == "proj.ds.t"
    assert s.bq_pr_reviews_table_id == "proj.ds.p"
    assert s.bq_team_velocity_table_id == "proj.ds.v"


def test_defaults_applied_when_not_specified():
    s = Settings(_env_file=None, GCP_PROJECT_ID="proj")
    assert s.bq_dataset == "flowmate"
    assert s.bq_tickets_table == "tickets"
    assert s.bq_pr_reviews_table == "pr_reviews"
    assert s.bq_team_velocity_table == "team_velocity"
    assert s.gemini_model == "gemini-3.6-flash"
    assert s.gcp_location == "us-central1"
