#!/usr/bin/env python3
"""Load the synthetic FlowMate tables (parquet) into BigQuery.

Creates the dataset/tables if they don't exist yet, using explicit schemas
(rather than autodetect) so column types stay stable regardless of the
sample of rows generated.

Usage:
    python scripts/load_synthetic_to_bigquery.py --truncate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings  # noqa: E402

TICKETS_SCHEMA = [
    bigquery.SchemaField("ticket_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("work_item_type", "STRING"),
    bigquery.SchemaField("state", "STRING"),
    bigquery.SchemaField("priority", "INTEGER"),
    bigquery.SchemaField("severity", "STRING"),
    bigquery.SchemaField("team", "STRING"),
    bigquery.SchemaField("sprint_id", "STRING"),
    bigquery.SchemaField("assigned_to", "STRING"),
    bigquery.SchemaField("created_by", "STRING"),
    bigquery.SchemaField("created_date", "TIMESTAMP"),
    bigquery.SchemaField("changed_date", "TIMESTAMP"),
    bigquery.SchemaField("state_entered_date", "TIMESTAMP"),
    bigquery.SchemaField("closed_date", "TIMESTAMP"),
    bigquery.SchemaField("area_path", "STRING"),
    bigquery.SchemaField("iteration_path", "STRING"),
    bigquery.SchemaField("story_points", "FLOAT"),
    bigquery.SchemaField("tags", "STRING"),
    bigquery.SchemaField("depends_on_ticket_id", "STRING"),
    bigquery.SchemaField("blocking_ticket_count", "INTEGER"),
    bigquery.SchemaField("pull_request_id", "STRING"),
    bigquery.SchemaField("is_blocked", "BOOLEAN"),
    bigquery.SchemaField("blocked_reason", "STRING"),
    bigquery.SchemaField("comment_count", "INTEGER"),
    bigquery.SchemaField("last_comment_date", "TIMESTAMP"),
]

PR_REVIEWS_SCHEMA = [
    bigquery.SchemaField("pr_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ticket_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("author", "STRING"),
    bigquery.SchemaField("reviewer", "STRING"),
    bigquery.SchemaField("team", "STRING"),
    bigquery.SchemaField("sprint_id", "STRING"),
    bigquery.SchemaField("created_date", "TIMESTAMP"),
    bigquery.SchemaField("review_requested_date", "TIMESTAMP"),
    bigquery.SchemaField("reviewed_date", "TIMESTAMP"),
    bigquery.SchemaField("review_status", "STRING"),
    bigquery.SchemaField("lines_added", "INTEGER"),
    bigquery.SchemaField("lines_removed", "INTEGER"),
    bigquery.SchemaField("lines_changed", "INTEGER"),
    bigquery.SchemaField("review_latency_hours", "FLOAT"),
]

TEAM_VELOCITY_SCHEMA = [
    bigquery.SchemaField("team", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("sprint_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("sprint_start_date", "TIMESTAMP"),
    bigquery.SchemaField("sprint_end_date", "TIMESTAMP"),
    bigquery.SchemaField("committed_points", "FLOAT"),
    bigquery.SchemaField("delivered_points", "FLOAT"),
    bigquery.SchemaField("blocker_count", "INTEGER"),
    bigquery.SchemaField("ticket_count", "INTEGER"),
    bigquery.SchemaField("miss_rate", "FLOAT"),
]

TABLES = [
    ("tickets.parquet", lambda: settings.bq_tickets_table_id, TICKETS_SCHEMA),
    ("pr_reviews.parquet", lambda: settings.bq_pr_reviews_table_id, PR_REVIEWS_SCHEMA),
    ("team_velocity.parquet", lambda: settings.bq_team_velocity_table_id, TEAM_VELOCITY_SCHEMA),
]


def ensure_dataset(client: bigquery.Client, dataset_id: str) -> None:
    full_id = f"{client.project}.{dataset_id}"
    try:
        client.get_dataset(full_id)
    except NotFound:
        dataset = bigquery.Dataset(full_id)
        dataset.location = settings.gcp_location
        client.create_dataset(dataset)
        print(f"Created dataset {full_id}")


def load_table(
    client: bigquery.Client,
    parquet_path: Path,
    table_id: str,
    schema: list[bigquery.SchemaField],
    truncate: bool,
) -> None:
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=(
            bigquery.WriteDisposition.WRITE_TRUNCATE
            if truncate
            else bigquery.WriteDisposition.WRITE_APPEND
        ),
    )

    with open(parquet_path, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=job_config)
    job.result()  # wait for completion, raises on failure

    table = client.get_table(table_id)
    print(f"Loaded {job.output_rows} rows -> {table_id} (total rows now: {table.num_rows})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--in-dir", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "synthetic",
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="Replace existing table contents instead of appending.",
    )
    args = parser.parse_args()

    client = bigquery.Client(project=settings.gcp_project_id)
    ensure_dataset(client, settings.bq_dataset)

    for filename, table_id_fn, schema in TABLES:
        parquet_path = args.in_dir / filename
        if not parquet_path.exists():
            raise SystemExit(
                f"{parquet_path} not found. Run scripts/generate_synthetic_dataset.py first."
            )
        load_table(client, parquet_path, table_id_fn(), schema, args.truncate)


if __name__ == "__main__":
    main()
