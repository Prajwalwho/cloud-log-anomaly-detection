"""
Create Kafka topics that a service needs, if they do not exist yet (idempotent).

Topics from the original design are created by kafka-init (docker-compose). alerts.events was added in Phase 8;
the alerting service and the API create it on start-up until it is moved into kafka-init (Phase 10).
"""
from __future__ import annotations

from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

SEVEN_DAYS_MS = 7 * 24 * 3600 * 1000


def ensure_topics(bootstrap_servers: str, topics: dict[str, int], retention_ms: int = SEVEN_DAYS_MS,
                  timeout_s: float = 10.0) -> list[str]:
    """topics: name -> partitions. Returns the names that were created. Raises if Kafka is unreachable."""
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    existing = admin.list_topics(timeout=timeout_s).topics
    missing = [NewTopic(name, num_partitions=partitions, replication_factor=1,
                        config={"retention.ms": str(retention_ms)})
               for name, partitions in topics.items() if name not in existing]
    if not missing:
        return []
    created = []
    for name, future in admin.create_topics(missing, operation_timeout=timeout_s).items():
        try:
            future.result()
            created.append(name)
        except KafkaException as exc:
            if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:     # created meanwhile by another service
                raise
    return created