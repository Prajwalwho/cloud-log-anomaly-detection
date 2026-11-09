"""
Integration test: the ingestion consumer validates messages, sends invalid ones to the
dead-letter topic, and commits offsets only after processing.

Requires the stack (.\\scripts\\start.ps1 up). Skipped automatically if Kafka is not reachable.
"""
import json
import os
import time
import uuid

import pytest
from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv

from backend.ingestion.config import IngestionSettings
from backend.ingestion.consumer import IngestionConsumer
from backend.log_generator.generator import LogGenerator

load_dotenv()
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

pytestmark = pytest.mark.integration


class ListSink:
    def __init__(self) -> None:
        self.events = []

    def write_batch(self, events) -> None:
        self.events.extend(events)


@pytest.fixture
def topics():
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
    try:
        admin.list_topics(timeout=5)
    except Exception:
        pytest.skip("Kafka not reachable; start the stack with .\\scripts\\start.ps1 up")

    suffix = uuid.uuid4().hex[:8]
    raw, deadletter = f"test-raw-{suffix}", f"test-dl-{suffix}"
    futures = admin.create_topics([NewTopic(raw, num_partitions=3, replication_factor=1),
                                   NewTopic(deadletter, num_partitions=1, replication_factor=1)])
    for future in futures.values():
        future.result(timeout=10)
    yield raw, deadletter
    for future in admin.delete_topics([raw, deadletter]).values():
        future.result(timeout=10)


def read_all(topic: str, expected: int, timeout_s: float = 20) -> list[dict]:
    consumer = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": f"read-{uuid.uuid4().hex[:8]}",
                         "auto.offset.reset": "earliest"})
    consumer.subscribe([topic])
    records, deadline = [], time.time() + timeout_s
    while len(records) < expected and time.time() < deadline:
        msg = consumer.poll(1.0)
        if msg is not None and not msg.error():
            records.append(json.loads(msg.value()))
    consumer.close()
    return records


def test_valid_to_sink_invalid_to_deadletter_offsets_committed(topics):
    raw_topic, deadletter_topic = topics
    events = [event for _, event in LogGenerator(rate=20, seed=5).events(5)]
    invalid = [
        b"not json",
        json.dumps({**events[0], "level": "CRITICAL"}).encode(),
        json.dumps({**events[0], "unexpected": 1}).encode(),
    ]

    producer = Producer({"bootstrap.servers": BOOTSTRAP})
    for event in events:
        producer.produce(raw_topic, key=event["service"].encode(), value=json.dumps(event).encode())
    for payload in invalid:
        producer.produce(raw_topic, value=payload)
    assert producer.flush(10) == 0

    group = f"test-ingestion-{uuid.uuid4().hex[:8]}"
    config = IngestionSettings(
        kafka_bootstrap_servers=BOOTSTRAP,
        kafka_topic_logs=raw_topic,
        kafka_topic_deadletter=deadletter_topic,
        ingestion_group_id=group,
    )
    sink = ListSink()
    stats = IngestionConsumer(sink, config).run(idle_exit_s=10, verbose=False)

    # Valid events reached the sink, invalid ones did not
    total = len(events) + len(invalid)
    assert stats.received == total
    assert stats.valid == len(events)
    assert stats.invalid == len(invalid)
    assert {str(e.event_id) for e in sink.events} == {e["event_id"] for e in events}

    # Invalid ones are in the dead-letter topic with a reason
    deadletters = read_all(deadletter_topic, expected=len(invalid))
    assert len(deadletters) == len(invalid)
    for record in deadletters:
        assert record["source_topic"] == raw_topic
        assert record["error"]
        assert record["raw_message"]

    # All offsets were committed after processing
    checker = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": group})
    partitions = checker.list_topics(raw_topic, timeout=10).topics[raw_topic].partitions
    committed = checker.committed([TopicPartition(raw_topic, p) for p in partitions], timeout=10)
    checker.close()
    assert sum(tp.offset for tp in committed if tp.offset >= 0) == total