"""Unit tests for log event validation and dead-letter records."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.ingestion.validator import (
    MAX_ERROR_LENGTH,
    build_deadletter_record,
    describe_error,
    validate_message,
)
from backend.log_generator.generator import LogGenerator


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def base(**changes) -> dict:
    event = {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "timestamp": iso(datetime.now(timezone.utc) - timedelta(minutes=1)),
        "service": "payment-service",
        "host": "node-2",
        "level": "INFO",
        "message": "Payment processed",
        "trace_id": "a91c4e7f",
        "endpoint": "POST /api/payments",
        "status_code": 200,
        "latency_ms": 142.0,
        "metadata": {},
    }
    event.update(changes)
    return event


def test_all_generator_events_are_valid():
    for _, event in LogGenerator(rate=20, seed=1).events(30):
        validate_message(json.dumps(event))


def test_valid_event_is_parsed():
    event = validate_message(json.dumps(base()))
    assert event.level == "INFO"
    assert event.timestamp.tzinfo == timezone.utc
    assert event.status_code == 200


def test_non_utc_timestamp_is_converted_to_utc():
    event = validate_message(json.dumps(base(timestamp="2026-01-01T15:45:30.123+05:30")))
    assert event.timestamp.tzinfo == timezone.utc
    assert event.timestamp.hour == 10 and event.timestamp.minute == 15


def test_optional_fields_may_be_omitted():
    data = base()
    for optional in ("trace_id", "endpoint", "status_code", "latency_ms", "metadata"):
        del data[optional]
    event = validate_message(json.dumps(data))
    assert event.metadata == {}


def _drop(field):
    return lambda d: d.pop(field)


def _set(**changes):
    return lambda d: d.update(changes)


@pytest.mark.parametrize(
    "change, field",
    [
        (_drop("level"), "level"),
        (_drop("event_id"), "event_id"),
        (_set(level="CRITICAL"), "level"),
        (_set(timestamp=iso(datetime.now(timezone.utc) + timedelta(hours=1))), "timestamp"),
        (_set(timestamp="2026-11-08T10:00:00"), "timestamp"),             # no timezone
        (_set(timestamp="yesterday"), "timestamp"),
        (_set(user="admin"), "user"),                                      # extra field
        (_set(latency_ms=-5), "latency_ms"),
        (_set(status_code="500"), "status_code"),                          # string, not int
        (_set(status_code=700), "status_code"),
        (_set(schema_version="2.0"), "schema_version"),
        (_set(message=""), "message"),
        (_set(message="x" * 10_001), "message"),
        (_set(event_id="not-a-uuid"), "event_id"),
        (_set(service="Payment Service"), "service"),                      # spaces/uppercase
    ],
)
def test_invalid_events_are_rejected(change, field):
    data = base()
    change(data)
    with pytest.raises(ValidationError) as info:
        validate_message(json.dumps(data))
    assert field in describe_error(info.value)


def test_invalid_json_is_rejected():
    with pytest.raises(ValidationError) as info:
        validate_message(b"this is not json {")
    assert "json" in describe_error(info.value).lower()


def test_empty_message_value_is_rejected():
    with pytest.raises(ValueError):
        validate_message(None)


def test_deadletter_record_follows_contract():
    record = build_deadletter_record(b"bad payload", "logs.raw", 1, 42, "level: invalid")
    assert set(record) == {"schema_version", "failed_at", "source_topic", "source_partition",
                           "source_offset", "error", "raw_message"}
    assert record["raw_message"] == "bad payload"
    assert record["source_offset"] == 42
    assert record["failed_at"].endswith("Z")


def test_deadletter_record_handles_binary_garbage():
    record = build_deadletter_record(b"\xff\xfe\x00", "logs.raw", 0, 1, "json: invalid")
    assert isinstance(record["raw_message"], str)


def test_error_description_is_truncated():
    assert len(describe_error(ValueError("x" * 5000))) <= MAX_ERROR_LENGTH