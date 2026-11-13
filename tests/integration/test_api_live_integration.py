"""
Full path through real Kafka: a message published to anomalies.detected reaches a /ws/live client.
Publishes one clearly marked test message (service api-gateway, reasons ["integration test"]).
"""
import json
import time
import uuid

import pytest
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient
from fastapi.testclient import TestClient

from backend.api.app.config import ApiSettings
from backend.api.app.main import create_app

pytestmark = pytest.mark.integration
SETTINGS = ApiSettings(live_ping_s=1.0)


def kafka_available() -> bool:
    try:
        topics = AdminClient({"bootstrap.servers": SETTINGS.kafka_bootstrap_servers}).list_topics(timeout=5).topics
        return SETTINGS.kafka_topic_anomalies in topics
    except Exception:
        return False


def test_anomaly_from_kafka_reaches_the_websocket():
    if not kafka_available():
        pytest.skip("Kafka not reachable; start the stack with .\\scripts\\start.ps1 up")
    anomaly_id = str(uuid.uuid4())
    message = {
        "schema_version": "1.0", "anomaly_id": anomaly_id, "detected_at": "2026-11-13T12:10:06.119Z",
        "service": "api-gateway", "window_start": "2026-11-13T12:09:00.000Z",
        "window_end": "2026-11-13T12:10:00.000Z", "anomaly_score": 0.6, "severity": "LOW",
        "model_name": "live-pca", "model_version": "1.1.0", "model_id": 5,
        "summary": {"reasons": ["integration test"]}, "sample_event_ids": [],
    }
    with TestClient(create_app(SETTINGS)) as client:
        assert client.app.state.listener.ready.wait(15), "listener did not attach to Kafka"
        with client.websocket_connect("/api/v1/ws/live") as ws:
            deadline = time.monotonic() + 5
            while client.app.state.hub.client_count < 1:
                assert time.monotonic() < deadline
                time.sleep(0.02)

            producer = Producer({"bootstrap.servers": SETTINGS.kafka_bootstrap_servers})
            producer.produce(SETTINGS.kafka_topic_anomalies, key=b"api-gateway", value=json.dumps(message).encode())
            assert producer.flush(10) == 0

            for _ in range(30):                     # pings arrive every second, so this never blocks for long
                event = ws.receive_json()
                if event["type"] == "anomaly.created" and event["data"]["id"] == anomaly_id:
                    break
            else:
                pytest.fail("anomaly did not arrive within 30 events")
    assert event["data"]["model"] == {"id": 5, "name": "live-pca", "version": "1.1.0"}
    assert event["data"]["summary"]["reasons"] == ["integration test"]