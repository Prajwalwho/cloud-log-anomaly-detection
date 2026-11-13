"""
Publishes new anomalies to Kafka topic anomalies.detected (contracts.md), keyed by service.

PostgreSQL is the source of truth: anomalies are published only after they are stored, and a failed publish
is counted and reported, not retried forever (the API reads anomalies from the database). The Kafka message
lets alerting and the live dashboard react immediately.
"""
from __future__ import annotations

import json
from datetime import datetime

from confluent_kafka import Producer

SCHEMA_VERSION = "1.0"


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def anomaly_message(anomaly: dict, model: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "anomaly_id": anomaly["anomaly_id"],
        "detected_at": _iso(anomaly["detected_at"]),
        "service": anomaly["service"],
        "window_start": _iso(anomaly["window_start"]),
        "window_end": _iso(anomaly["window_end"]),
        "anomaly_score": round(float(anomaly["anomaly_score"]), 6),
        "severity": anomaly["severity"],
        "model": {"id": model["id"], "name": model["name"], "version": model["version"]},
        "summary": anomaly["summary"],
        "sample_event_ids": anomaly["sample_event_ids"],
    }


class AnomalyPublisher:
    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self.topic = topic
        self.failed = 0
        self.delivered = 0
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": "detection-publisher",
            "acks": "all",
            "enable.idempotence": True,
            "linger.ms": 20,
        })

    def _on_delivery(self, err, _msg) -> None:
        if err is None:
            self.delivered += 1
        else:
            self.failed += 1
            print(f"  [ERROR] anomaly not published: {err}")

    def publish(self, anomalies: list[dict], model: dict) -> None:
        for anomaly in anomalies:
            self._producer.produce(
                self.topic, key=anomaly["service"].encode(),
                value=json.dumps(anomaly_message(anomaly, model), default=str).encode(),
                on_delivery=self._on_delivery,
            )
        self._producer.flush(10)