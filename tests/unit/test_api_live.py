"""Live feed without Kafka: pings, fan-out to every client, slow clients dropped, message conversion."""
import asyncio
import time

from fastapi.testclient import TestClient

from backend.api.app.config import ApiSettings
from backend.api.app.main import create_app
from backend.api.app.realtime import CLOSE, LiveHub, to_anomaly_item

BASE = dict(postgres_port=1, elasticsearch_url="http://localhost:1", kafka_bootstrap_servers="localhost:1",
            dependency_timeout_s=1.0, live_kafka_enabled=False)
MESSAGE = {
    "schema_version": "1.0", "anomaly_id": "c4e8a2f1-6b3d-4a9e-8c7f-0d1e2b3a4c5d",
    "detected_at": "2026-11-13T12:10:06.119Z", "service": "payment-service",
    "window_start": "2026-11-13T12:09:00.000Z", "window_end": "2026-11-13T12:10:00.000Z",
    "anomaly_score": 0.84, "severity": "CRITICAL", "model_name": "live-pca", "model_version": "1.1.0",
    "model_id": 5, "summary": {"reasons": ["error rate 42.2%"]}, "sample_event_ids": [],
}


def wait_for_clients(client: TestClient, n: int) -> None:
    deadline = time.monotonic() + 5
    while client.app.state.hub.client_count < n:
        assert time.monotonic() < deadline, "clients did not register"
        time.sleep(0.02)


def test_ping_arrives():
    with TestClient(create_app(ApiSettings(**BASE, live_ping_s=0.2))) as client:
        with client.websocket_connect("/api/v1/ws/live") as ws:
            assert ws.receive_json() == {"type": "ping", "data": {}}


def test_event_reaches_every_client():
    event = {"type": "anomaly.created", "data": to_anomaly_item(MESSAGE)}
    with TestClient(create_app(ApiSettings(**BASE, live_ping_s=60))) as client:
        with client.websocket_connect("/api/v1/ws/live") as a, client.websocket_connect("/api/v1/ws/live") as b:
            wait_for_clients(client, 2)
            client.app.state.hub.publish_threadsafe(event)
            assert a.receive_json() == event
            assert b.receive_json() == event


def test_slow_client_is_dropped_without_affecting_others():
    async def scenario():
        hub = LiveHub(asyncio.get_running_loop(), queue_size=2)
        fast, slow = hub.register(), hub.register()
        for n in range(3):
            hub.publish({"n": n})
            assert fast.get_nowait() == {"n": n}          # the fast client keeps up
        assert hub.client_count == 1 and hub.dropped_clients == 1
        assert slow.get_nowait() is CLOSE                  # the slow client is told to close
    asyncio.run(scenario())


def test_kafka_message_becomes_anomaly_item():
    item = to_anomaly_item(MESSAGE)
    assert set(item) == {"id", "service", "detected_at", "window_start", "window_end", "anomaly_score",
                         "severity", "model", "summary", "alert_id", "feedback"}
    assert item["id"] == MESSAGE["anomaly_id"]
    assert item["model"] == {"id": 5, "name": "live-pca", "version": "1.1.0"}
    assert item["alert_id"] is None and item["feedback"] is None