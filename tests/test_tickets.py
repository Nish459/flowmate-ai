from synthetic.entities import TEAM_ROSTER_SIZES


def test_row_count_matches_request(small_tickets_df):
    from tests.conftest import SMALL_DATASET_SIZE

    assert len(small_tickets_df) == SMALL_DATASET_SIZE


def test_ticket_ids_are_unique(small_tickets_df):
    assert small_tickets_df["ticket_id"].is_unique


def test_changed_date_never_before_created_date(small_tickets_df):
    assert (small_tickets_df["changed_date"] >= small_tickets_df["created_date"]).all()


def test_closed_date_present_iff_terminal_state(small_tickets_df):
    terminal = small_tickets_df["state"].isin(["Resolved", "Closed"])
    assert small_tickets_df.loc[terminal, "closed_date"].notna().all()
    assert small_tickets_df.loc[~terminal, "closed_date"].isna().all()


def test_closed_date_never_before_created_date(small_tickets_df):
    closed = small_tickets_df.dropna(subset=["closed_date"])
    assert (closed["closed_date"] >= closed["created_date"]).all()


def test_changed_date_equals_closed_date_for_terminal_tickets(small_tickets_df):
    closed = small_tickets_df.dropna(subset=["closed_date"])
    assert (closed["changed_date"] == closed["closed_date"]).all()


def test_blocking_ticket_count_matches_actual_dependency_graph(small_tickets_df):
    expected = small_tickets_df["depends_on_ticket_id"].value_counts()
    for ticket_id, count in zip(small_tickets_df["ticket_id"], small_tickets_df["blocking_ticket_count"]):
        assert count == expected.get(ticket_id, 0)


def test_dependencies_only_point_to_strictly_earlier_tickets(small_tickets_df):
    created_by_id = small_tickets_df.set_index("ticket_id")["created_date"]
    deps = small_tickets_df.dropna(subset=["depends_on_ticket_id"])
    for ticket_id, dep_id in zip(deps["ticket_id"], deps["depends_on_ticket_id"]):
        assert created_by_id[dep_id] < created_by_id[ticket_id]


def test_every_ticket_has_a_known_team(small_tickets_df):
    assert set(small_tickets_df["team"].unique()) <= set(TEAM_ROSTER_SIZES.keys())


def test_only_bug_tickets_have_severity(small_tickets_df):
    bug = small_tickets_df[small_tickets_df["work_item_type"] == "Bug"]
    non_bug = small_tickets_df[small_tickets_df["work_item_type"] != "Bug"]
    assert bug["severity"].notna().all()
    assert non_bug["severity"].isna().all()


def test_blocked_state_implies_is_blocked_flag(small_tickets_df):
    assert small_tickets_df.loc[small_tickets_df["state"] == "Blocked", "is_blocked"].all()
