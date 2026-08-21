#!/usr/bin/env python3
"""Load synthetic tickets (parquet) into BigQuery.

Creates the dataset/table if they don't exist yet, using an explicit
schema (rather than autodetect) so column types stay stable regardless
of the sample of rows generated.

Usage:
    python scripts/load_tickets_to_bigquery.py --in data/synthetic/tickets.parquet
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
    bigquery.SchemaField("reviewer", "STRING"),
    bigquery.SchemaField("review_status", "STRING"),
    bigquery.SchemaField("review_requested_date", "TIMESTAMP"),
    bigquery.SchemaField("pull_request_id", "STRING"),
    bigquery.SchemaField("is_blocked", "BOOLEAN"),
    bigquery.SchemaField("blocked_reason", "STRING"),
    bigquery.SchemaField("comment_count", "INTEGER"),
    bigquery.SchemaField("last_comment_date", "TIMESTAMP"),
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


def load(parquet_path: Path, truncate: bool) -> None:
    client = bigquery.Client(project=settings.gcp_project_id)
    ensure_dataset(client, settings.bq_dataset)

    job_config = bigquery.LoadJobConfig(
        schema=TICKETS_SCHEMA,
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=(
            bigquery.WriteDisposition.WRITE_TRUNCATE
            if truncate
            else bigquery.WriteDisposition.WRITE_APPEND
        ),
    )

    with open(parquet_path, "rb") as f:
        job = client.load_table_from_file(f, settings.bq_tickets_table_id, job_config=job_config)
    job.result()  # wait for completion, raises on failure

    table = client.get_table(settings.bq_tickets_table_id)
    print(f"Loaded {job.output_rows} rows -> {settings.bq_tickets_table_id} (total rows now: {table.num_rows})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--in", dest="input_path", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "synthetic" / "tickets.parquet",
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="Replace existing table contents instead of appending.",
    )
    args = parser.parse_args()

    if not args.input_path.exists():
        raise SystemExit(
            f"{args.input_path} not found. Run scripts/generate_synthetic_tickets.py first."
        )

    load(args.input_path, args.truncate)


if __name__ == "__main__":
    main()
