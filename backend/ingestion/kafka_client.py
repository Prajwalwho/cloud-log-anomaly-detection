"""
Kafka client factories for the ingestion service.
"""
from __future__ import annotations

from confluent_kafka import Consumer, KafkaException, Producer


def create_consumer(bootstrap_servers: str, group_id: str) -> Consumer:
    return Consumer({
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "client.id": "ingestion",
        # The first time this group runs, start from the oldest retained message (no data loss)
        "auto.offset.reset": "earliest",
        # Offsets are committed manually, only after a batch has been fully processed
        "enable.auto.commit": False,
    })


def create_producer(bootstrap_servers: str, client_id: str) -> Producer:
    return Producer({
        "bootstrap.servers": bootstrap_servers,
        "client.id": client_id,
        "acks": "all",
        "enable.idempotence": True,
        "linger.ms": 20,
    })


def require_topics(client: Consumer | Producer, topics: list[str], timeout_s: float = 10.0) -> None:
    """Fail fast with a clear message if Kafka is unreachable or a topic is missing."""
    try:
        metadata = client.list_topics(timeout=timeout_s)
    except KafkaException as exc:
        raise RuntimeError(
            f"Kafka not reachable ({exc}). Is the stack running? Start it with: .\\scripts\\start.ps1 up"
        ) from exc

    missing = [t for t in topics if t not in metadata.topics or metadata.topics[t].error is not None]
    if missing:
        raise RuntimeError(f"Kafka topics missing: {missing}. Topics are created by: .\\scripts\\start.ps1 up")