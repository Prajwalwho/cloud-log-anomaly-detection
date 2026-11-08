"""
Read messages from a Kafka topic and check them against the contracts.

Checks:
  - every message is valid JSON with the required log fields
  - message key == event service
  - each service always lands in the same partition (keying contract, contracts.md 4.1)

Usage:
    python scripts/kafka_peek.py
    python scripts/kafka_peek.py --show 5
    python scripts/kafka_peek.py --topic logs.deadletter --show 10
"""
import argparse
import json
import os
import sys
import time
import uuid
from collections import Counter, defaultdict

from confluent_kafka import Consumer, KafkaException, TopicPartition
from dotenv import load_dotenv

load_dotenv()

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REQUIRED_FIELDS = {"schema_version", "event_id", "timestamp", "service", "host", "level", "message"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect messages in a Kafka topic.")
    parser.add_argument("--topic", default="logs.raw")
    parser.add_argument("--max", type=int, default=20000, help="maximum messages to read (default: %(default)s)")
    parser.add_argument("--show", type=int, default=0, help="print the first N messages")
    parser.add_argument("--idle", type=float, default=5.0, help="stop after this many seconds without messages")
    args = parser.parse_args()

    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": f"peek-{uuid.uuid4().hex[:8]}",   # fresh group: always reads from the beginning
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })

    try:
        metadata = consumer.list_topics(args.topic, timeout=10)
    except KafkaException as exc:
        print(f"[FAIL] Kafka not reachable at {BOOTSTRAP}: {exc}")
        return 1
    topic_metadata = metadata.topics.get(args.topic)
    if topic_metadata is None or topic_metadata.error is not None:
        print(f"[FAIL] Topic '{args.topic}' does not exist")
        return 1

    print(f"Topic '{args.topic}' — messages stored per partition:")
    for partition in sorted(topic_metadata.partitions):
        low, high = consumer.get_watermark_offsets(TopicPartition(args.topic, partition), timeout=10)
        print(f"  partition {partition}: {high - low}")

    consumer.subscribe([args.topic])
    by_partition: dict[int, Counter] = defaultdict(Counter)
    read = invalid = shown = 0
    last_message = time.time()

    while read < args.max and time.time() - last_message < args.idle:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"  consumer error: {msg.error()}")
            continue
        last_message = time.time()
        read += 1

        try:
            event = json.loads(msg.value())
            key = msg.key().decode("utf-8") if msg.key() else None
            valid = REQUIRED_FIELDS <= event.keys() and key == event["service"]
        except (ValueError, AttributeError, TypeError):
            valid = False
        if not valid:
            invalid += 1
            continue

        by_partition[msg.partition()][event["service"]] += 1
        if shown < args.show:
            print(f"  [partition {msg.partition()} offset {msg.offset()} key={key}] "
                  f"{event['timestamp']} {event['level']:<5} {event['message']}")
            shown += 1

    consumer.close()

    print(f"\nRead {read} messages ({invalid} invalid)")
    print("Services per partition:")
    for partition in sorted(by_partition):
        services = ", ".join(f"{s}={n}" for s, n in sorted(by_partition[partition].items()))
        print(f"  partition {partition}: {services}")

    partitions_of: dict[str, set[int]] = defaultdict(set)
    for partition, counter in by_partition.items():
        for service in counter:
            partitions_of[service].add(partition)
    split = {s: sorted(p) for s, p in partitions_of.items() if len(p) > 1}

    ok = True
    if split:
        print(f"[FAIL] Services spread over several partitions: {split}")
        ok = False
    elif partitions_of:
        print("[OK] Each service is always in the same partition (key = service)")
    if invalid:
        print(f"[FAIL] {invalid} messages are invalid (bad JSON, missing fields or key != service)")
        ok = False
    elif read:
        print("[OK] All messages are valid log events with key = service")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())