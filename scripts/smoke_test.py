"""
Smoke test: verifies that Kafka and PostgreSQL are reachable from the host
and match the project contracts.

Usage:  python scripts/smoke_test.py
"""
import os
import sys
import time
import uuid

import psycopg
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PG_CONNINFO = (
    f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'cla_db')} "
    f"user={os.getenv('POSTGRES_USER', 'cla_user')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'change_me')}"
)

EXPECTED_TOPICS = {"logs.raw", "logs.deadletter", "anomalies.detected"}
EXPECTED_TABLES = {"services", "model_registry", "detection_windows", "anomalies", "alerts"}


def check_kafka() -> None:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})

    # 1. Required topics exist
    existing = set(admin.list_topics(timeout=10).topics)
    missing = EXPECTED_TOPICS - existing
    if missing:
        raise RuntimeError(f"Missing Kafka topics: {sorted(missing)}")

    # 2. Produce and consume a message on a temporary topic
    test_topic = f"smoke-test-{uuid.uuid4().hex[:8]}"
    admin.create_topics([NewTopic(test_topic, num_partitions=1, replication_factor=1)])[test_topic].result(timeout=10)

    try:
        payload = f"smoke-{uuid.uuid4()}".encode()
        producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})
        producer.produce(test_topic, key=b"smoke", value=payload)
        producer.flush(10)

        consumer = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": f"smoke-{uuid.uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
        })
        consumer.subscribe([test_topic])

        received = None
        deadline = time.time() + 20
        while time.time() < deadline:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise RuntimeError(f"Consumer error: {msg.error()}")
            received = msg.value()
            break
        consumer.close()

        if received != payload:
            raise RuntimeError("Test message was not received back from Kafka")
    finally:
        admin.delete_topics([test_topic])[test_topic].result(timeout=10)

    print(f"[OK] Kafka at {KAFKA_BOOTSTRAP}: topics present, produce/consume works")


def check_postgres() -> None:
    with psycopg.connect(PG_CONNINFO, connect_timeout=10) as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
        tables = {r[0] for r in rows}
        missing = EXPECTED_TABLES - tables
        if missing:
            raise RuntimeError(f"Missing tables: {sorted(missing)}")

        service_count = conn.execute("SELECT count(*) FROM services").fetchone()[0]

    print(f"[OK] PostgreSQL: all {len(EXPECTED_TABLES)} tables present, {service_count} services seeded")


def main() -> int:
    failures = 0
    for name, check in [("Kafka", check_kafka), ("PostgreSQL", check_postgres)]:
        try:
            check()
        except Exception as exc:  # report every failure, not just the first
            print(f"[FAIL] {name}: {exc}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())