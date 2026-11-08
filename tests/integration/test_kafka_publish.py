"""
Integration test: generated events published to Kafka arrive intact and keyed by service.

Requires the stack (.\\scripts\\start.ps1 up). Skipped automatically if Kafka is not reachable.
"""
import json
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import pytest
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv

from backend.log_generator.generator import LogGenerator
from backend.log_generator.producer import KafkaLogPublisher

load_dotenv()
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

pytestmark = pytest.mark.integration


@pytest.fixture
def admin() -> AdminClient:
    client = AdminClient({"bootstrap.servers": BOOTSTRAP})
    try:
        client.list_topics(timeout=5)
    except Exception:
        pytest.skip("Kafka not reachable; start the stack with .\\scripts\\start.ps1 up")
    return client


@pytest.fixture
def temp_topic(admin: AdminClient):
    name = f"test-logs-{uuid.uuid4().hex[:8]}"
    admin.create_topics([NewTopic(name, num_partitions=3, replication_factor=1)])[name].result(timeout=10)
    yield name
    admin.delete_topics([name])[name].result(timeout=10)


def test_events_arrive_intact_and_keyed_by_service(temp_topic: str):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [event for _, event in LogGenerator(rate=20, seed=11, start=start).events(10)]

    publisher = KafkaLogPublisher(BOOTSTRAP, temp_topic)
    assert publisher.check_connection() == 3
    for event in events:
        publisher.publish(event)
    assert publisher.flush() == 0
    assert publisher.delivered == len(events)
    assert publisher.failed == 0

    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": f"test-{uuid.uuid4().hex[:8]}",
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([temp_topic])

    received: dict[str, dict] = {}
    partitions_of: dict[str, set[int]] = defaultdict(set)
    deadline = time.time() + 30
    while len(received) < len(events) and time.time() < deadline:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        event = json.loads(msg.value())
        assert msg.key().decode("utf-8") == event["service"]
        received[event["event_id"]] = event
        partitions_of[event["service"]].add(msg.partition())
    consumer.close()

    assert received == {event["event_id"]: event for event in events}
    assert all(len(partitions) == 1 for partitions in partitions_of.values())


def test_missing_topic_is_reported_clearly(admin: AdminClient):
    publisher = KafkaLogPublisher(BOOTSTRAP, f"does-not-exist-{uuid.uuid4().hex[:8]}")
    with pytest.raises(RuntimeError, match="does not exist"):
        publisher.check_connection()