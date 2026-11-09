"""
Send deliberately invalid messages (and one valid control message) to logs.raw,
to test validation and the dead-letter topic.

Usage:
    python scripts/send_invalid_logs.py
"""
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = "logs.raw"


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def valid_event(**changes) -> dict:
    event = {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "timestamp": iso(datetime.now(timezone.utc)),
        "service": "inventory-service",
        "host": "node-3",
        "level": "INFO",
        "message": "Validation test message",
        "trace_id": None,
        "endpoint": None,
        "status_code": None,
        "latency_ms": None,
        "metadata": {},
    }
    event.update(changes)
    return event


def without(field: str) -> dict:
    event = valid_event()
    del event[field]
    return event


CASES: list[tuple[str, str]] = [
    ("valid event (control)", json.dumps(valid_event())),
    ("not JSON", "this is not json {"),
    ("missing required field 'level'", json.dumps(without("level"))),
    ("unknown level 'CRITICAL'", json.dumps(valid_event(level="CRITICAL"))),
    ("timestamp 1 hour in the future", json.dumps(valid_event(timestamp=iso(datetime.now(timezone.utc) + timedelta(hours=1))))),
    ("extra top-level field 'user'", json.dumps(valid_event(user="admin"))),
    ("negative latency", json.dumps(valid_event(latency_ms=-5))),
    ("status code as a string", json.dumps(valid_event(status_code="500"))),
    ("status code out of range", json.dumps(valid_event(status_code=700))),
    ("wrong schema version", json.dumps(valid_event(schema_version="2.0"))),
    ("empty message text", json.dumps(valid_event(message=""))),
]


def main() -> int:
    producer = Producer({"bootstrap.servers": BOOTSTRAP})
    for description, payload in CASES:
        producer.produce(TOPIC, key=b"validation-test", value=payload.encode("utf-8"))
        print(f"  sent: {description}")
    remaining = producer.flush(10)
    if remaining:
        print(f"[FAIL] {remaining} messages not delivered")
        return 1
    print(f"\nSent {len(CASES)} messages to '{TOPIC}': 1 valid, {len(CASES) - 1} invalid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())