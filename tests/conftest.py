import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
for path in (str(ROOT), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from generate_synthetic_dataset import generate_dataset  # noqa: E402

# Smaller than the default 800 (for speed) but large enough that the
# engineered patterns (see synthetic/patterns.py) are still statistically
# visible. Session-scoped since the dataset is deterministic under this
# seed and expensive-ish to regenerate per test.
SMALL_DATASET_SIZE = 800
SMALL_DATASET_SEED = 42


@pytest.fixture(scope="session")
def small_dataset():
    return generate_dataset(SMALL_DATASET_SIZE, SMALL_DATASET_SEED, horizon_days=90)


@pytest.fixture(scope="session")
def small_tickets_df(small_dataset):
    return small_dataset[0]


@pytest.fixture(scope="session")
def small_pr_reviews_df(small_dataset):
    return small_dataset[1]


@pytest.fixture(scope="session")
def small_team_velocity_df(small_dataset):
    return small_dataset[2]
