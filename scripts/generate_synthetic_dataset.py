#!/usr/bin/env python3
"""Generate the synthetic FlowMate dataset: tickets, pr_reviews, team_velocity.

Three BigQuery-shaped tables, generated together so they share teams,
sprints, and a single RNG -- keeping ticket_id/sprint_id/team values valid
join keys across all three. See scripts/synthetic/patterns.py for the
deliberately engineered bottleneck signal (not random noise) that the
Bottleneck Detector agent will later need to find.

Usage:
    python scripts/generate_synthetic_dataset.py --num-tickets 800 --seed 42
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from faker import Faker

from synthetic import pr_reviews, team_velocity, tickets, validate
from synthetic.entities import build_sprints, build_teams, utc_now


def generate_dataset(num_tickets: int, seed: int, horizon_days: int):
    random.seed(seed)
    rng = np.random.default_rng(seed)
    fake = Faker()
    Faker.seed(seed)

    now = utc_now()
    teams = build_teams(fake)
    sprints = build_sprints(now, horizon_days)
    sprint_ids = {s.sprint_id for s in sprints}

    tickets_df = tickets.generate_tickets(num_tickets, rng, fake, teams, sprints, now)
    pr_reviews_df = pr_reviews.generate_pr_reviews(tickets_df, rng, fake, teams, now)
    tickets_df["pull_request_id"] = tickets_df["ticket_id"].map(
        pr_reviews_df.drop_duplicates("ticket_id").set_index("ticket_id")["pr_id"]
    )
    team_velocity_df = team_velocity.generate_team_velocity(tickets_df, teams, sprints)

    validate.validate(tickets_df, pr_reviews_df, team_velocity_df, sprint_ids)

    return tickets_df, pr_reviews_df, team_velocity_df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-tickets", type=int, default=800)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--horizon-days", type=int, default=90, help="How far back tickets can be created.")
    parser.add_argument(
        "--out-dir", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "synthetic",
    )
    args = parser.parse_args()

    tickets_df, pr_reviews_df, team_velocity_df = generate_dataset(args.num_tickets, args.seed, args.horizon_days)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    tickets_df.to_parquet(args.out_dir / "tickets.parquet", index=False)
    pr_reviews_df.to_parquet(args.out_dir / "pr_reviews.parquet", index=False)
    team_velocity_df.to_parquet(args.out_dir / "team_velocity.parquet", index=False)

    print(f"tickets:        {len(tickets_df):>4} rows -> {args.out_dir / 'tickets.parquet'}")
    print(f"pr_reviews:     {len(pr_reviews_df):>4} rows -> {args.out_dir / 'pr_reviews.parquet'}")
    print(f"team_velocity:  {len(team_velocity_df):>4} rows -> {args.out_dir / 'team_velocity.parquet'}")
    print()
    print(tickets_df["state"].value_counts())


if __name__ == "__main__":
    main()
