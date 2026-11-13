"""Stored documents keep the contract timestamp format (contracts.md §1): ms precision, Z."""
import json
import uuid

from backend.ingestion.es_sink import format_timestamp_ms, to_document
from backend.ingestion.validator import LogEvent


def event(timestamp: str) -> LogEvent:
    return LogEvent.model_validate_json(json.dumps({
        "schema_version": "1.0", "event_id": str(uuid.uuid4()), "timestamp": timestamp,
        "service": "payment-service", "host": "node-2", "level": "INFO", "message": "test",
    }))


def test_generator_timestamp_is_stored_unchanged():
    document = to_document(event("2026-11-13T12:11:53.074Z"), ingested_at="2026-11-13T12:11:54.000Z")
    assert document["timestamp"] == "2026-11-13T12:11:53.074Z"


def test_whole_seconds_get_three_decimals():
    assert to_document(event("2026-11-13T12:11:53Z"), "x")["timestamp"] == "2026-11-13T12:11:53.000Z"


def test_other_time_zones_are_stored_in_utc():
    assert to_document(event("2026-11-13T17:41:53.074+05:30"), "x")["timestamp"] == "2026-11-13T12:11:53.074Z"


def test_format_helper():
    from datetime import datetime, timezone
    assert format_timestamp_ms(datetime(2026, 11, 13, 12, 11, 53, 74999, tzinfo=timezone.utc)) == \
        "2026-11-13T12:11:53.074Z"