"""
Log endpoints against the running stack, with their own test data: five log events on 2001-01-02 in a separate
daily index, removed afterwards.
"""
import uuid

import pytest
from elasticsearch import Elasticsearch
from fastapi.testclient import TestClient

from backend.api.app.config import ApiSettings
from backend.api.app.main import create_app

pytestmark = pytest.mark.integration
SETTINGS = ApiSettings()
ES_INDEX = f"{SETTINGS.elasticsearch_index_prefix}-2001.01.02"
RANGE = {"from": "2001-01-02T09:00:00Z", "to": "2001-01-02T11:00:00Z"}
# second, service, level, message, trace_id
EVENTS = [
    (1, "payment-service", "ERROR", "Payment failed for order 1: card processor timeout", "t1"),
    (2, "payment-service", "INFO", "Payment processed for order 1", "t1"),
    (3, "api-gateway", "ERROR", "POST /api/payments failed with status 502", "t1"),
    (4, "auth-service", "INFO", "Token validated for user u1", "t2"),
    (5, "inventory-service", "WARN", "Slow response on stock check", "t3"),
]


@pytest.fixture(scope="module")
def data():
    es = Elasticsearch(SETTINGS.elasticsearch_url)
    if not es.ping():
        pytest.skip("Elasticsearch not reachable; start the stack with .\\scripts\\start.ps1 up")
    ids = []
    for second, service, level, message, trace in EVENTS:
        event_id = str(uuid.uuid4())
        es.index(index=ES_INDEX, id=event_id, document={
            "schema_version": "1.0", "event_id": event_id, "timestamp": f"2001-01-02T10:00:0{second}.000Z",
            "service": service, "host": "node-1", "level": level, "message": message, "trace_id": trace})
        ids.append(event_id)
    es.indices.refresh(index=ES_INDEX)
    yield ids
    es.indices.delete(index=ES_INDEX, ignore_unavailable=True)
    es.close()


@pytest.fixture(scope="module")
def client(data):
    with TestClient(create_app(SETTINGS)) as test_client:
        yield test_client


def search(client, **params):
    response = client.get("/api/v1/logs", params={**RANGE, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_newest_first_in_log_event_schema(client):
    body = search(client)
    assert body["total"] == 5
    assert [e["service"] for e in body["items"]][:2] == ["inventory-service", "auth-service"]
    assert "ingested_at" not in body["items"][0]


def test_keyword_filters(client):
    assert search(client, service="payment-service")["total"] == 2
    assert search(client, level="error,WARN")["total"] == 3
    assert search(client, trace_id="t1")["total"] == 3


def test_full_text_requires_all_words(client):
    assert search(client, q="failed")["total"] == 2
    assert search(client, q="payment failed")["total"] == 1      # "payments" in the gateway line is another word


def test_pagination_and_result_window_limit(client):
    body = search(client, size=2, page=3)
    assert body["total"] == 5 and len(body["items"]) == 1
    assert client.get("/api/v1/logs", params={**RANGE, "page": 51, "size": 200}).status_code == 400


def test_unknown_level_is_rejected(client):
    assert client.get("/api/v1/logs", params={**RANGE, "level": "CRITICAL"}).status_code == 400


def test_single_log_event(client, data):
    response = client.get(f"/api/v1/logs/{data[0]}")
    assert response.status_code == 200 and response.json()["event_id"] == data[0]
    assert client.get(f"/api/v1/logs/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/logs/not-a-uuid").status_code == 422