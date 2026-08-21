"""Engineered ("cheat") signal baked into the synthetic dataset.

The Bottleneck Detector agent (later milestone) is a Gemini-reasoning-over-
BigQuery-history feature. Uniformly random synthetic data gives it nothing
real to find, so this module centralizes every deliberate, non-random
pattern in one place with concrete parameters -- both so the numbers are
easy to defend in a demo, and so there is a single source of truth for what
counts as "ground truth" bottleneck signal when the detector is built.

Three patterns, each targeting a different reasoning angle in the doc:

1. Slow team x ticket type/tag: DevOps is slow on Bug tickets tagged
   migration/database -- a `GROUP BY team, work_item_type` query surfaces an
   obvious outlier.
2. Slow reviewer: one specific reviewer has much higher review latency and a
   higher changes-requested rate, regardless of author/team -- a
   `GROUP BY reviewer` query surfaces this cleanly, uncorrelated with team.
3. Recent-sprint miss-rate spike: Bug tickets created in the most recent few
   sprints have a depressed close rate. The project doc calls this a "Q3"
   effect; our synthetic timeline is relative to "now" rather than a real
   calendar quarter, so RECENT_SPRINT_WINDOW stands in for that concept.

Effect sizes are chosen large enough (2.5-4x) to be obvious in a simple
aggregation or chart, but spread across dozens of rows with normal per-row
noise on top -- not a single suspicious record.
"""

# --- Pattern 1: slow team x ticket type/tag ---------------------------------

SLOW_TEAM = "DevOps"
SLOW_TEAM_TICKET_TYPE = "Bug"
SLOW_TEAM_TAGS = {"migration", "database"}

# How much more likely a DevOps ticket is to be a Bug, and to carry one of
# SLOW_TEAM_TAGS, versus the dataset-wide baseline -- needed so the pattern
# shows up in enough rows (target: ~70-100 out of 800+ tickets) for a GROUP
# BY to be statistically obvious rather than a handful of outliers.
SLOW_TEAM_BUG_TYPE_WEIGHT = 0.55
SLOW_TEAM_TAG_INCLUSION_PROB = 0.55
BASELINE_TAG_INCLUSION_PROB = 0.15

SLOW_TEAM_CYCLE_TIME_MULTIPLIER = 2.75

# State distribution for tickets matching the slow-team pattern: biased away
# from Closed, toward Blocked/Active, versus the dataset-wide STATE_WEIGHTS.
SLOW_TEAM_STATE_WEIGHTS = {
    "New": 0.05,
    "Active": 0.30,
    "In Review": 0.10,
    "Blocked": 0.25,
    "Resolved": 0.10,
    "Closed": 0.20,
}

# --- Pattern 2: slow reviewer ------------------------------------------------

# Index into the full, alphabetically-sorted engineer roster (deterministic
# under any fixed seed, rather than a hardcoded name).
SLOW_REVIEWER_INDEX = 2

BASELINE_REVIEW_LATENCY_MEAN_HOURS = 18.0
BASELINE_REVIEW_LATENCY_SIGMA = 0.6
SLOW_REVIEWER_LATENCY_MEAN_HOURS = 65.0
SLOW_REVIEWER_LATENCY_SIGMA = 0.5

BASELINE_CHANGES_REQUESTED_RATE = 0.15
SLOW_REVIEWER_CHANGES_REQUESTED_RATE = 0.35

# --- Pattern 3: recent-sprint miss-rate spike -------------------------------

RECENT_SPRINT_WINDOW = 3  # last N sprints stand in for the doc's "Q3"
BASELINE_BUG_CLOSE_RATE = 0.70
RECENT_WINDOW_BUG_CLOSE_RATE = 0.38

# Bug tickets get their own state distribution (separate from the generic
# STATE_WEIGHTS used for other work item types), so patterns 1 and 3 -- both
# of which only apply to Bugs -- have a clean baseline to modulate.
BUG_STATE_WEIGHTS_BASELINE = {
    "New": 0.05, "Active": 0.10, "In Review": 0.10,
    "Blocked": 0.05, "Resolved": 0.30, "Closed": 0.40,
}  # close rate 0.70, matches BASELINE_BUG_CLOSE_RATE
BUG_STATE_WEIGHTS_RECENT_WINDOW = {
    "New": 0.05, "Active": 0.25, "In Review": 0.12,
    "Blocked": 0.20, "Resolved": 0.15, "Closed": 0.23,
}  # close rate 0.38, matches RECENT_WINDOW_BUG_CLOSE_RATE
