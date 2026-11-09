"""Unit tests for Elasticsearch index naming, documents and the index template."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from backend.ingestion.es_sink import build_index_template, index_name, to_document
from backend.ingestion.validator import validate_message

CONTRACT_FIELDS = {"schema_version", "event_id", "timestamp", "service", "host", "level", "message",
                   "trace_id", "endpoint", "status_code", "latency_ms", "metadata"}


def sample_event():
    now = datetime.now(timezone.utc) - timedelta(minutes=1)
    return validate_message(json.dumps({
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        "service": "payment-service",
        "host": "node-2",
        "level": "ERROR",
        "message": "Payment failed for order 1: timeout",
        "trace_id": "abc123",
        "endpoint": "POST /internal/payments",
        "status_code": 504,
        "latency_ms": 3012.5,
        "metadata": {"db_host": "primary"},
    }))


def test_index_name_uses_utc_day():
    assert index_name("logs", datetime(2026, 11, 9, 23, 30, tzinfo=timezone.utc)) == "logs-2026.11.09"
    ist = timezone(timedelta(hours=5, minutes=30))
    # 02:00 IST on Nov 10 is still Nov 9 in UTC
    assert index_name("logs", datetime(2026, 11, 10, 2, 0, tzinfo=ist)) == "logs-2026.11.09"


def test_document_contains_all_fields_and_ingested_at():
    document = to_document(sample_event(), "2026-11-09T10:00:00.000Z")
    assert set(document) == CONTRACT_FIELDS | {"ingested_at"}
    assert isinstance(document["event_id"], str)
    assert document["timestamp"].endswith("Z")
    assert document["metadata"] == {"db_host": "primary"}


def test_template_is_configured_for_a_single_node():
    template = build_index_template("logs")
    settings = template["template"]["settings"]
    assert template["index_patterns"] == ["logs-*"]
    assert settings["number_of_replicas"] == 0
    assert settings["number_of_shards"] == 1
    assert template["template"]["mappings"]["dynamic"] == "strict"


def test_template_maps_every_document_field():
    properties = build_index_template("logs")["template"]["mappings"]["properties"]
    document = to_document(sample_event(), "2026-11-09T10:00:00.000Z")
    assert set(document) <= set(properties)
    assert properties["service"]["type"] == "keyword"
    assert properties["message"]["type"] == "text"
    assert properties["timestamp"]["type"] == "date"