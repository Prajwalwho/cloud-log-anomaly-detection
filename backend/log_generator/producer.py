"""
Kafka publisher for generated log events.

Publishes each event to the logs.raw topic as compact JSON, keyed by service
name (contracts.md, Section 4.1), so all logs of one service go to the same
partition and stay in order.
"""
from __future__ import annotations

import json

from confluent_kafka import KafkaError, KafkaException, Message, Producer


class KafkaLogPublisher:
    def __init__(self, bootstrap_servers: str, topic: str, client_id: str = "log-generator") -> None:
        self.topic = topic
        self.bootstrap_servers = bootstrap_servers
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            # Durability: a message counts as sent only after the broker has stored it,
            # and retries after network errors never create duplicates.
            "acks": "all",
            "enable.idempotence": True,
            # Throughput: batch messages for up to 20 ms and compress each batch.
            "linger.ms": 20,
            "compression.type": "lz4",
            # Same key -> same partition as Kafka's Java clients (murmur2 hashing).
            "partitioner": "murmur2_random",
        })
        self.delivered = 0
        self.failed = 0
        self.last_error: str | None = None

    def check_connection(self, timeout_s: float = 10.0) -> int:
        """Fail fast if Kafka is unreachable or the topic is missing. Returns the partition count."""
        try:
            metadata = self._producer.list_topics(topic=self.topic, timeout=timeout_s)
        except KafkaException as exc:
            raise RuntimeError(
                f"Kafka not reachable at {self.bootstrap_servers} ({exc}). "
                f"Is the stack running? Start it with: .\\scripts\\start.ps1 up"
            ) from exc

        topic_metadata = metadata.topics.get(self.topic)
        if topic_metadata is None or topic_metadata.error is not None:
            raise RuntimeError(
                f"Kafka topic '{self.topic}' does not exist. "
                f"Topics are created by: .\\scripts\\start.ps1 up"
            )
        return len(topic_metadata.partitions)

    def publish(self, event: dict) -> None:
        """Queue one event for sending. Delivery is confirmed asynchronously."""
        key = event["service"].encode("utf-8")
        value = json.dumps(event, separators=(",", ":")).encode("utf-8")
        while True:
            try:
                self._producer.produce(self.topic, key=key, value=value, on_delivery=self._on_delivery)
                break
            except BufferError:
                # Local send queue is full: process delivery reports until space frees up.
                self._producer.poll(0.5)
        self._producer.poll(0)   # trigger delivery callbacks for completed sends

    def flush(self, timeout_s: float = 30.0) -> int:
        """Wait until all queued messages are delivered. Returns the number still undelivered."""
        return self._producer.flush(timeout_s)

    def _on_delivery(self, err: KafkaError | None, msg: Message) -> None:
        if err is None:
            self.delivered += 1
        else:
            self.failed += 1
            self.last_error = str(err)

    def __enter__(self) -> KafkaLogPublisher:
        return self

    def __exit__(self, *exc_info) -> None:
        self.flush()