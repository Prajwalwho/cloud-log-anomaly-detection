"""Unit tests for the anomalies.detected message format (contracts.md §5.3)."""
import re
from datetime import datetime, timezone

from backend.detection.publisher import anomaly_message, iso_ms

T = datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)
CONTRACT_FIELDS = {"schema_version", "anomaly_id", "detected_at", "service", "window_start", "window_end",
                   "anomaly_score", "severity", "model_name", "model_version", "summary", "sample_event_ids"}
OPTIONAL_FIELDS = {"model_id"}
MS_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def message():
    anomaly = {"anomaly_id": "a1", "detected_at": datetime(2026, 11, 13, 8, 0, 49, 77522, tzinfo=timezone.utc),
               "service": "payment-service", "window_start": T, "window_end": T, "anomaly_score": 0.8333333333,
               "severity": "CRITICAL", "summary": {"reasons": ["error rate 39.0%"]}, "sample_event_ids": ["e1"]}
    return anomaly_message(anomaly, {"id": 5, "name": "live-pca", "version": "1.1.0"})


def test_message_has_exactly_the_contract_fields():
    fields = set(message())
    assert CONTRACT_FIELDS <= fields
    assert fields - CONTRACT_FIELDS <= OPTIONAL_FIELDS


def test_model_fields_are_flat():
    m = message()
    assert (m["model_name"], m["model_version"], m["model_id"]) == ("live-pca", "1.1.0", 5)
    assert "model" not in m


def test_timestamps_have_millisecond_precision():
    m = message()
    for field in ("detected_at", "window_start", "window_end"):
        assert MS_TIMESTAMP.match(m[field]), m[field]
    assert m["detected_at"] == "2026-11-13T08:00:49.077Z"
    assert m["window_start"] == "2026-11-13T08:00:00.000Z"


def test_iso_ms_converts_other_time_zones_to_utc():
    from datetime import timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    assert iso_ms(datetime(2026, 11, 13, 13, 30, tzinfo=ist)) == "2026-11-13T08:00:00.000Z"