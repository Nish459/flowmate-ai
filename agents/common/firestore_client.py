"""Shared Firestore access for FlowMate -- currently just the Standup
Writer's daily snapshot cache at standups/{engineer}/days/{yyyy-mm-dd}
(see CLAUDE.md's "Sprint recall + what's next" section for the design).
"""

from __future__ import annotations

import sys
from pathlib import Path

from google.cloud import firestore

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import settings  # noqa: E402

_client: firestore.Client | None = None


def _get_client() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=settings.gcp_project_id)
    return _client


def _days_ref(engineer: str):
    return (
        _get_client()
        .collection(settings.firestore_standups_collection)
        .document(engineer)
        .collection("days")
    )


def write_standup_snapshot(engineer: str, date: str, snapshot: dict) -> None:
    """Write one engineer's structured standup for `date` (YYYY-MM-DD).

    `date` and `engineer` are denormalized into the document body (not just
    the path) so get_standup_history can range-query on a plain field
    instead of needing FieldPath.document_id() tricks.
    """
    _days_ref(engineer).document(date).set({**snapshot, "date": date, "engineer": engineer})


def get_standup_history(engineer: str, start_date: str, end_date: str) -> list[dict]:
    """Return an engineer's cached standups between start_date and end_date
    (inclusive, both YYYY-MM-DD), ordered chronologically."""
    query = (
        _days_ref(engineer)
        .where("date", ">=", start_date)
        .where("date", "<=", end_date)
        .order_by("date")
    )
    return [doc.to_dict() for doc in query.stream()]
