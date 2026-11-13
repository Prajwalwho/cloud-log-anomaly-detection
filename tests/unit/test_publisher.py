"""Unit tests for the anomaly message format."""
from datetime import datetime, timezone

from backend.detection.publisher import anomaly_message

T = datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)


def test_message_fields_and_utc_format():
    anomaly = {"anomaly_id": "a1", "detected_at": T, "service": "payment-service", "window_start": T,
               "window_end": T, "anomaly_score": 0.8333333333, "severity": "CRITICAL",
               "summary": {"reasons": ["error rate 39.0%"]}, "sample_event_ids": ["e1"]}
    message = anomaly_message(anomaly, {"id": 5, "name": "live-pca", "version": "1.1.0"})
    assert set(message) == {"schema_version", "anomaly_id", "detected_at", "service", "window_start",
                            "window_end", "anomaly_score", "severity", "model", "summary", "sample_event_ids"}
    assert message["detected_at"] == "2026-11-13T08:00:00Z"
    assert message["model"] == {"id": 5, "name": "live-pca", "version": "1.1.0"}
    assert message["anomaly_score"] == 0.833333