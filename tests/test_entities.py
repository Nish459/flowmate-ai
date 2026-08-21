import pytest
from faker import Faker

from synthetic.entities import (
    TEAM_ROSTER_SIZES,
    all_engineers,
    build_sprints,
    build_teams,
    engineer_team,
    sprint_for_date,
    utc_now,
)


def test_build_teams_matches_fixed_roster():
    fake = Faker()
    Faker.seed(1)
    teams = build_teams(fake)
    assert {t.name for t in teams} == set(TEAM_ROSTER_SIZES.keys())
    for team in teams:
        assert len(team.engineers) == TEAM_ROSTER_SIZES[team.name]


def test_engineers_are_unique_across_teams():
    fake = Faker()
    Faker.seed(2)
    teams = build_teams(fake)
    engineers = all_engineers(teams)
    assert len(engineers) == len(set(engineers))


def test_engineer_team_resolves_membership():
    fake = Faker()
    Faker.seed(3)
    teams = build_teams(fake)
    engineer = teams[0].engineers[0]
    assert engineer_team(teams, engineer) == teams[0].name


def test_engineer_team_raises_for_unknown_engineer():
    fake = Faker()
    Faker.seed(4)
    teams = build_teams(fake)
    with pytest.raises(ValueError):
        engineer_team(teams, "Nobody Real")


def test_sprints_are_contiguous_with_no_gaps():
    now = utc_now()
    sprints = build_sprints(now, horizon_days=90)
    assert len(sprints) >= 6
    for prev, nxt in zip(sprints, sprints[1:]):
        assert prev.end_date == nxt.start_date
        assert nxt.sequence_number == prev.sequence_number + 1


def test_sprint_for_date_finds_the_containing_sprint():
    now = utc_now()
    sprints = build_sprints(now, horizon_days=90)
    target = sprints[2]
    midpoint = target.start_date + (target.end_date - target.start_date) / 2
    assert sprint_for_date(sprints, midpoint).sprint_id == target.sprint_id
