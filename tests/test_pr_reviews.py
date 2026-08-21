def test_pr_reviews_only_reference_known_tickets(small_tickets_df, small_pr_reviews_df):
    assert set(small_pr_reviews_df["ticket_id"]) <= set(small_tickets_df["ticket_id"])


def test_only_eligible_tickets_get_pr_rows(small_tickets_df, small_pr_reviews_df):
    eligible_ids = set(
        small_tickets_df[
            small_tickets_df["state"].isin(["In Review", "Resolved", "Closed"])
            & small_tickets_df["work_item_type"].isin(["Task", "Bug", "User Story", "Feature"])
        ]["ticket_id"]
    )
    assert set(small_pr_reviews_df["ticket_id"]) <= eligible_ids


def test_pending_reviews_have_no_reviewed_date_or_latency(small_pr_reviews_df):
    pending = small_pr_reviews_df[small_pr_reviews_df["review_status"] == "Pending"]
    assert pending["reviewed_date"].isna().all()
    assert pending["review_latency_hours"].isna().all()


def test_non_pending_reviews_have_consistent_latency(small_pr_reviews_df):
    reviewed = small_pr_reviews_df.dropna(subset=["reviewed_date"]).copy()
    assert len(reviewed) > 0
    computed_hours = (reviewed["reviewed_date"] - reviewed["review_requested_date"]).dt.total_seconds() / 3600
    assert (computed_hours - reviewed["review_latency_hours"]).abs().max() < 1e-6


def test_lines_changed_equals_added_plus_removed(small_pr_reviews_df):
    assert (
        small_pr_reviews_df["lines_changed"] == small_pr_reviews_df["lines_added"] + small_pr_reviews_df["lines_removed"]
    ).all()


def test_review_requested_date_not_before_created_date(small_pr_reviews_df):
    assert (small_pr_reviews_df["review_requested_date"] >= small_pr_reviews_df["created_date"]).all()
