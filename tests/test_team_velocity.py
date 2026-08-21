def test_no_duplicate_team_sprint_rows(small_team_velocity_df):
    assert not small_team_velocity_df.duplicated(subset=["team", "sprint_id"]).any()


def test_every_team_covers_the_same_set_of_sprints(small_team_velocity_df):
    sprint_sets = small_team_velocity_df.groupby("team")["sprint_id"].apply(lambda s: frozenset(s))
    assert sprint_sets.nunique() == 1


def test_delivered_never_exceeds_committed(small_team_velocity_df):
    assert (small_team_velocity_df["delivered_points"] <= small_team_velocity_df["committed_points"] + 1e-9).all()


def test_miss_rate_matches_formula(small_team_velocity_df):
    nonzero = small_team_velocity_df[small_team_velocity_df["committed_points"] > 0]
    expected = (1 - nonzero["delivered_points"] / nonzero["committed_points"]).round(4)
    assert (expected - nonzero["miss_rate"]).abs().max() < 1e-6


def test_zero_committed_gives_zero_miss_rate(small_team_velocity_df):
    zero_committed = small_team_velocity_df[small_team_velocity_df["committed_points"] == 0]
    if len(zero_committed):
        assert (zero_committed["miss_rate"] == 0).all()
