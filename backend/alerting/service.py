"""
Alerting service (Phase 8): anomalies.detected -> alerts in PostgreSQL -> alerts.events (+ Telegram).

- Consumer group alerting-group; a NEW group starts at the end of the topic (old and test messages are skipped);
  after that, committed offsets let it resume where it stopped.
- Offsets are committed after the alerts are stored and their events published. A crash before that replays the
  messages, which is safe: an anomaly that already has an alert is skipped ("duplicate"). The same holds when the
  group membership is lost after a long pause: the commit is skipped with a warning (common/kafka_commit.py).
- Every created/updated/resolved alert is published to alerts.events; the API forwards it to /ws/live.
- Every alert_resolve_check_s, alerts without anomalies for alert_resolve_after_s are resolved.
- Telegram (rules.notification_kind): one message when an alert reaches HIGH, one when a notified alert becomes
  CRITICAL, one when a notified alert is resolved. A failed send leaves notification_sent false, so the next update
  of that alert tries again. Messages are sent from a background thread (background.py, Day 43): storing and
  publishing alerts never waits for Telegram; a successful send is recorded (notified_at) and published as an update.

alerts.events message:
    {"schema_version": "1.0", "type": "alert.created" | "alert.updated", "anomaly_id": "..." | null,
     "alert": {alert item as in api-contracts.md §3.8}}

Usage (from the project root, stack running):
    python -m backend.alerting.service
    python -m backend.alerting.service --idle-exit 60
    python -m backend.alerting.service --no-telegram          # e.g. during a load test
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter

import psycopg
from confluent_kafka import Consumer, Producer

from ..common.kafka_commit import commit_safely
from ..common.kafka_topics import ensure_topics
from .background import BackgroundSender
from .config import AlertingSettings
from .notifier import TelegramNotifier
from .rules import notification_kind
from .store import AlertStore

SCHEMA_VERSION = "1.0"


def alert_event(event_type: str, alert: dict, anomaly_id: str | None) -> dict:
    return {"schema_version": SCHEMA_VERSION, "type": event_type, "anomaly_id": anomaly_id, "alert": alert}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alerting service: group anomalies into alerts.")
    parser.add_argument("--idle-exit", type=float, help="stop after this many seconds without messages")
    parser.add_argument("--group", help="consumer group (default from settings: alerting-group)")
    parser.add_argument("--no-telegram", action="store_true",
                        help="do not send Telegram messages (tests, load tests); alerts are stored as usual")
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
    notifier = (TelegramNotifier(None, None) if args.no_telegram
                else TelegramNotifier(settings.telegram_token, settings.telegram_chat_id))
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

    def publish(event_type: str, alert: dict, anomaly_id: str | None) -> None:
        producer.produce(settings.kafka_topic_alerts, key=alert["service"].encode(),
                         value=json.dumps(alert_event(event_type, alert, anomaly_id)).encode())

    def after_sent(kind: str, alert: dict) -> None:
        """Runs on the sender thread after Telegram accepted a message."""
        print(f"  notified       {alert['service']:<18} {kind}")
        if kind != "resolved":
            publish("alert.updated", store.mark_notified(alert["id"]), None)

    sender = BackgroundSender(notifier, after_sent)

    def notified(alert: dict) -> bool:
        """Told already, or a message for it is on its way."""
        return alert["notification_sent"] or sender.is_pending(alert["id"])

    counts: Counter = Counter()
    last_message = time.monotonic()
    next_resolve = time.monotonic() + settings.alert_resolve_check_s
    print(f"Alerting service: '{settings.kafka_topic_anomalies}' -> PostgreSQL alerts -> "
          f"'{settings.kafka_topic_alerts}', group '{group}', grouping gap {settings.alert_group_gap_s:.0f} s, "
          f"min severity to open {settings.alert_min_severity}, resolve after {settings.alert_resolve_after_s:.0f} s "
          f"quiet. Telegram: {'on (' + settings.notify_min_severity + ' and above)' if notifier.enabled else 'off'}. "
          f"Ctrl+C to stop.")
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
                    kind = notification_kind(outcome.result, alert["severity"], outcome.previous_severity,
                                             notified(alert), settings.notify_min_severity)
                    publish(outcome.event_type, alert, anomaly["anomaly_id"])
                    if kind:
                        sender.submit(kind, alert)
                    print(f"  {outcome.event_type:<14} {alert['service']:<18} {alert['severity']:<8} "
                          f"x{alert['occurrence_count']:<3} {alert['title']}  ({alert['message']})")
                elif outcome.result == "below_threshold":
                    print(f"  (no alert)     {anomaly['service']:<18} {anomaly['severity']:<8} below "
                          f"{settings.alert_min_severity}")
            if messages:
                producer.flush(10)
                commit_safely(consumer, label="alerting")
                last_message = time.monotonic()

            if time.monotonic() >= next_resolve:
                for alert in store.resolve_quiet(settings.alert_resolve_after_s):
                    counts["resolved"] += 1
                    print(f"  resolved       {alert['service']:<18} {alert['severity']:<8} "
                          f"x{alert['occurrence_count']:<3} {alert['title']}")
                    publish("alert.updated", alert, None)
                    if notified(alert):
                        sender.submit("resolved", alert)
                producer.flush(10)
                next_resolve = time.monotonic() + settings.alert_resolve_check_s

            if args.idle_exit is not None and time.monotonic() - last_message >= args.idle_exit:
                break
    except KeyboardInterrupt:
        pass
    finally:
        unsent = sender.close(15)
        if unsent:
            print(f"  [WARN] {unsent} Telegram message(s) not sent before shutdown")
        producer.flush(10)
        consumer.close()

    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing processed"
    print(f"\n{summary}; Telegram sent {notifier.sent}, failed {notifier.failed}"
          + (f", dropped {sender.dropped}" if sender.dropped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())