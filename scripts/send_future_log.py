"""
Robustness test: publish ONE otherwise well-formed log event with a timestamp in 2030 to logs.raw.

Expected:
- detection service: prints "[WARN] skipped event with timestamp 2030-..." and counts it as "future";
  windows keep closing normally and "late" stays 0.
- ingestion: rejects it (timestamp more than 5 minutes in the future) and sends it to the dead-letter topic.

Usage (from the project root, while the stack, ingestion and detection are running):
    python scripts/send_future_log.py
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from confluent_kafka import Producer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.config import DetectionSettings  # noqa: E402


def main() -> int:
    settings = DetectionSettings()
    event = {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "timestamp": "2030-01-01T00:00:00Z",
        "service": "api-gateway",
        "host": "node-1",
        "level": "INFO",
        "message": "Robustness test: event with a timestamp far in the future",
    }
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
    producer.produce(settings.kafka_topic_logs, key=b"api-gateway", value=json.dumps(event).encode())
    remaining = producer.flush(10)
    if remaining:
        print("[FAIL] event not delivered (is the stack running?)")
        return 1
    print(f"[OK] sent event {event['event_id']} with timestamp {event['timestamp']} to {settings.kafka_topic_logs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())