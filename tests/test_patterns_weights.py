"""Pure sanity checks on the probability-weight tables. Catches a broken
distribution (weights that no longer sum to 1) immediately, rather than as
a subtly-skewed dataset discovered much later.
"""

import pytest

from synthetic import patterns
from synthetic.tickets import SEVERITIES, SEVERITY_WEIGHTS, STATE_WEIGHTS, WORK_ITEM_WEIGHTS


@pytest.mark.parametrize(
    "weights",
    [
        STATE_WEIGHTS,
        patterns.BUG_STATE_WEIGHTS_BASELINE,
        patterns.BUG_STATE_WEIGHTS_RECENT_WINDOW,
        patterns.SLOW_TEAM_STATE_WEIGHTS,
    ],
    ids=["state_weights", "bug_baseline", "bug_recent_window", "slow_team_state_weights"],
)
def test_state_weight_dicts_sum_to_one(weights):
    assert sum(weights.values()) == pytest.approx(1.0)


def test_work_item_weights_sum_to_one_and_align_with_types():
    assert sum(WORK_ITEM_WEIGHTS) == pytest.approx(1.0)


def test_severity_weights_sum_to_one_and_align_with_severities():
    assert len(SEVERITIES) == len(SEVERITY_WEIGHTS)
    assert sum(SEVERITY_WEIGHTS) == pytest.approx(1.0)


def test_bug_close_rate_constants_match_their_weight_dicts():
    baseline_close = patterns.BUG_STATE_WEIGHTS_BASELINE["Resolved"] + patterns.BUG_STATE_WEIGHTS_BASELINE["Closed"]
    recent_close = (
        patterns.BUG_STATE_WEIGHTS_RECENT_WINDOW["Resolved"] + patterns.BUG_STATE_WEIGHTS_RECENT_WINDOW["Closed"]
    )
    assert baseline_close == pytest.approx(patterns.BASELINE_BUG_CLOSE_RATE)
    assert recent_close == pytest.approx(patterns.RECENT_WINDOW_BUG_CLOSE_RATE)
