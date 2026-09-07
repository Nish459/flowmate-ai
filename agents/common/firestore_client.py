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


def _scans_ref():
    return _get_client().collection(settings.firestore_scans_collection)


def write_scan_snapshot(snapshot: dict) -> None:
    """Cache the latest agent scan output so the dashboard can render instantly
    instead of waiting out a live multi-minute scan."""
    _scans_ref().document("latest").set(snapshot)


def get_latest_scan() -> dict | None:
    """Return the cached scan output, or None if no scan has been cached yet."""
    doc = _scans_ref().document("latest").get()
    return doc.to_dict() if doc.exists else None


def _panels_ref():
    return _get_client().collection(settings.firestore_panels_collection)


def write_panels_snapshot(snapshot: dict) -> None:
    """Cache the latest structured ticket/PR/standup tables so the dashboard's
    tables render instantly instead of waiting on live BigQuery reads (~3s for
    5 queries -- fine for an explicit refresh, not for every page load)."""
    _panels_ref().document("latest").set(snapshot)


def get_latest_panels() -> dict | None:
    """Return the cached structured panel data, or None if never cached."""
    doc = _panels_ref().document("latest").get()
    return doc.to_dict() if doc.exists else None


def _personal_generated_ref(engineer: str):
    return (
        _get_client()
        .collection(settings.firestore_standups_collection)
        .document(engineer)
        .collection("personal_generated")
    )


def write_personal_standup(engineer: str, date: str, result: dict) -> None:
    """Cache one engineer's on-demand, LLM-generated personal standup for
    `date` (YYYY-MM-DD). Deliberately a separate subcollection from
    write_standup_snapshot's `days` -- that one is the deterministic
    Python-computed snapshot Standup History browses; conflating the two
    would mean this LLM narrative and that structured record could
    overwrite each other."""
    _personal_generated_ref(engineer).document(date).set(result)


def get_personal_standup(engineer: str, date: str) -> dict | None:
    """Return the cached personal standup for `date`, or None if this
    engineer hasn't generated one yet today."""
    doc = _personal_generated_ref(engineer).document(date).get()
    return doc.to_dict() if doc.exists else None


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
