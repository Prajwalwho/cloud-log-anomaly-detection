"""
Elasticsearch access for the API.

Logs are stored in daily indices <prefix>-YYYY.MM.DD with document _id = event_id (elasticsearch-design.md).
Looking documents up by _id does not depend on field mappings.

Timestamps are returned in the contract format (ms precision, Z). Documents ingested before the Day 29 ingestion
fix carry six decimals ("…53.074000Z"); they are normalised here, so API clients always see one format.
"""
from __future__ import annotations

from datetime import datetime

from elasticsearch import Elasticsearch

from .timeutil import iso_ms

INTERNAL_FIELDS = {"ingested_at"}       # added by ingestion, not part of the log event contract


def logs_index_pattern(prefix: str) -> str:
    return f"{prefix}-*"


def normalise_timestamp(value: str) -> str:
    try:
        return iso_ms(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (TypeError, ValueError):
        return value                    # leave anything unexpected unchanged rather than failing the request


def to_log_event(source: dict) -> dict:
    """A stored document in the log event schema of contracts.md §2."""
    event = {key: value for key, value in source.items() if key not in INTERNAL_FIELDS}
    if isinstance(event.get("timestamp"), str):
        event["timestamp"] = normalise_timestamp(event["timestamp"])
    return event


def fetch_logs_by_ids(es: Elasticsearch, index: str, ids: list[str]) -> tuple[list[dict], str | None]:
    """
    Log events for the given ids, in the order of `ids`; ids no longer stored are omitted.
    Returns (logs, error); error is set (and logs empty) if Elasticsearch cannot be reached.
    """
    if not ids:
        return [], None
    try:
        response = es.search(index=index, query={"ids": {"values": ids}}, size=len(ids),
                             ignore_unavailable=True, allow_no_indices=True)
    except Exception:
        return [], "Elasticsearch unavailable"
    by_id = {hit["_id"]: to_log_event(hit["_source"]) for hit in response["hits"]["hits"]}
    return [by_id[i] for i in ids if i in by_id], None