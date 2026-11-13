"""
Alerting service (Phase 8): anomalies.detected -> alerts in PostgreSQL -> alerts.events.

- Consumer group alerting-group; a NEW group starts at the end of the topic (old and test messages are skipped);
  after that, committed offsets let it resume where it stopped.
- Offsets are committed after the alerts are stored and their events published. A crash before that replays the
  messages, which is safe: an anomaly that already has an alert is skipped ("duplicate").
- Every created/updated alert is published to alerts.events; the API forwards it to /ws/live.

alerts.events message (contracts.md will document it on Day 32):
    {"schema_version": "1.0", "type": "alert.created" | "alert.updated", "anomaly_id": "...",
     "alert": {alert item as in api-contracts.md §3.8}}

Usage (from the project root, stack running):
    python -m backend.alerting.service
    python -m backend.alerting.service --idle-exit 60
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter

import psycopg
from confluent_kafka import Consumer, Producer

from ..common.kafka_topics import ensure_topics
from .config import AlertingSettings
from .store import AlertStore

SCHEMA_VERSION = "1.0"


def alert_event(event_type: str, alert: dict, anomaly_id: str) -> dict:
    return {"schema_version": SCHEMA_VERSION, "type": event_type, "anomaly_id": anomaly_id, "alert": alert}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alerting service: group anomalies into alerts.")
    parser.add_argument("--idle-exit", type=float, help="stop after this many seconds without messages")
    parser.add_argument("--group", help="consumer group (default from settings: alerting-group)")
    args = parser.parse_args(argv)
    settings = AlertingSettings()

    try:
        with psycopg.connect(settings.postgres_conninfo):
            pass
    except Exception as exc:
        print(f"[FAIL] PostgreSQL not reachable ({exc}). Start the stack: .\\scripts\\start.ps1 up")
        return 1
    try:
        created = ensure_topics(settings.kafka_bootstrap_servers, {settings.kafka_topic_alerts: 1})
    except Exception as exc:
        print(f"[FAIL] Kafka not reachable ({exc}). Start the stack: .\\scripts\\start.ps1 up")
        return 1
    if created:
        print(f"Created Kafka topic {', '.join(created)}")

    store = AlertStore(settings.postgres_conninfo, settings.alert_group_gap_s, settings.alert_min_severity)
    group = args.group or settings.alerting_group_id
    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": group,
        "client.id": "alerting",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([settings.kafka_topic_anomalies])
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers, "client.id": "alerting",
                         "acks": "all", "enable.idempotence": True, "linger.ms": 20})

    counts: Counter = Counter()
    last_message = time.monotonic()
    print(f"Alerting service: '{settings.kafka_topic_anomalies}' -> PostgreSQL alerts -> "
          f"'{settings.kafka_topic_alerts}', group '{group}', grouping gap {settings.alert_group_gap_s:.0f} s, "
          f"min severity to open {settings.alert_min_severity}. Ctrl+C to stop.")
    try:
        while True:
            messages = consumer.consume(num_messages=100, timeout=1.0)
            for msg in messages:
                if msg.error():
                    continue
                try:
                    anomaly = json.loads(msg.value())
                    outcome = store.process(anomaly)
                except (ValueError, KeyError, TypeError):
                    counts["invalid"] += 1
                    continue
                counts[outcome.result] += 1
                if outcome.event_type:
                    alert = outcome.alert
                    producer.produce(settings.kafka_topic_alerts, key=alert["service"].encode(),
                                     value=json.dumps(alert_event(outcome.event_type, alert,
                                                                  anomaly["anomaly_id"])).encode())
                    print(f"  {outcome.event_type:<14} {alert['service']:<18} {alert['severity']:<8} "
                          f"x{alert['occurrence_count']:<3} {alert['title']}  ({alert['message']})")
                elif outcome.result == "below_threshold":
                    print(f"  (no alert)     {anomaly['service']:<18} {anomaly['severity']:<8} below "
                          f"{settings.alert_min_severity}")
            if messages:
                producer.flush(10)
                consumer.commit(asynchronous=False)
                last_message = time.monotonic()
            if args.idle_exit is not None and time.monotonic() - last_message >= args.idle_exit:
                break
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush(10)
        consumer.close()

    print("\n" + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) if counts else "\nNo anomalies received")
    return 0


if __name__ == "__main__":
    sys.exit(main())