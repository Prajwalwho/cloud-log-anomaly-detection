"""
Live detection service (Phase 6, detection-design.md).

    logs.raw (own consumer group) -> Drain (model's saved parser state) -> 60-s windows per service
    -> active model (LiveDetector) -> judge (flag, no-logs rule, severity, reasons)
    -> PostgreSQL (detection_windows, anomalies) -> Kafka anomalies.detected

Window closing: per-partition event-time watermark (watermark.py). A partition is "caught up" when it has
been read up to its high-water mark (Kafka). While any partition is behind, windows close only up to the
minimum latest event time of the lagging partitions (or not at all if one has delivered nothing yet); when
all are caught up, wall-clock time is used. Windows close at watermark minus grace.

Delivery: offsets are committed only for events whose windows are closed and written (OffsetTracker), so a
restart replays the open windows instead of losing them. Storing is idempotent (store.py). Anomalies are
published after they are stored; PostgreSQL is the source of truth.

The first window after start-up is partial (it began before the first event was read) and is not scored.
Minutes without any traffic are stored without anomalies, not printed, and reported once.

Usage (from the project root):
    python -m backend.detection.service
    python -m backend.detection.service --idle-exit 60 --group detection-replay
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

from confluent_kafka import Consumer, KafkaException, TopicPartition

from .config import DetectionSettings
from .offsets import OffsetTracker
from .package import load_package
from .pipeline import parse_timestamp
from .publisher import AnomalyPublisher
from .registry import active_model
from .scoring.judge import judge_windows
from .store import DetectionStore
from .watermark import PartitionWatermark
from .windowing import WindowAggregator

SHORT = {"api-gateway": "gateway", "auth-service": "auth", "order-service": "order",
         "payment-service": "payment", "inventory-service": "inventory"}


def caught_up_partitions(consumer: Consumer, assigned: list[TopicPartition],
                         next_offset: dict[tuple[str, int], int]) -> set[tuple[str, int]]:
    """Partitions read up to their high-water mark (no unread data right now)."""
    result = set()
    for tp in assigned:
        key = (tp.topic, tp.partition)
        low, high = consumer.get_watermark_offsets(TopicPartition(tp.topic, tp.partition), timeout=5, cached=False)
        position = next_offset.get(key)
        if position is None:                         # nothing read from this partition in this run yet
            committed = consumer.committed([TopicPartition(tp.topic, tp.partition)], timeout=5)[0].offset
            position = committed if committed >= 0 else low
        if position >= high:
            result.add(key)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live detection service.")
    parser.add_argument("--idle-exit", type=float, help="stop after this many seconds without logs")
    parser.add_argument("--group", help="consumer group (default from settings: detection-group)")
    args = parser.parse_args(argv)
    settings = DetectionSettings()

    try:
        model = active_model(settings.postgres_conninfo)
    except Exception as exc:
        print(f"[FAIL] PostgreSQL not reachable ({exc}). Start the stack: .\\scripts\\start.ps1 up")
        return 1
    if model is None:
        print("[FAIL] No active model in model_registry. Train one: python -m backend.detection.train ...")
        return 1
    detector, miner, metadata = load_package(Path(model["file_path"]))
    store = DetectionStore(settings.postgres_conninfo)

    group = args.group or settings.detection_group_id
    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": group,
        "client.id": "detection",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    try:
        topics = consumer.list_topics(timeout=10).topics
    except KafkaException as exc:
        print(f"[FAIL] Kafka not reachable ({exc}). Start the stack: .\\scripts\\start.ps1 up")
        return 1
    for topic in (settings.kafka_topic_logs, settings.kafka_topic_anomalies):
        if topic not in topics:
            print(f"[FAIL] Topic {topic} missing. Start the stack: .\\scripts\\start.ps1 up")
            return 1
    consumer.subscribe([settings.kafka_topic_logs])
    publisher = AnomalyPublisher(settings.kafka_bootstrap_servers, settings.kafka_topic_anomalies)

    aggregator = WindowAggregator(settings.window_s, services=settings.service_list)
    tracker = OffsetTracker()
    watermark = PartitionWatermark()
    next_offset: dict[tuple[str, int], int] = {}
    grace = timedelta(seconds=settings.grace_s)
    first_event: float | None = None
    last_message = time.monotonic()
    events = invalid = windows_stored = anomalies_created = 0
    warned_idle = False

    print(f"Detection service: model {model['name']} {model['version']} (id {model['id']}), "
          f"group '{group}', topic '{settings.kafka_topic_logs}' -> '{settings.kafka_topic_anomalies}'. "
          f"Ctrl+C to stop.")
    try:
        while True:
            messages = consumer.consume(num_messages=500, timeout=1.0)
            for msg in messages:
                if msg.error():
                    continue
                next_offset[(msg.topic(), msg.partition())] = msg.offset() + 1
                try:
                    event = json.loads(msg.value())
                    ts = parse_timestamp(event["timestamp"])
                    service, level, text = event["service"], event["level"], event["message"]
                except Exception:
                    tracker.add(msg.topic(), msg.partition(), msg.offset(), float("-inf"))
                    invalid += 1
                    continue
                template_id = miner.add_log_message(text)["cluster_id"]
                aggregator.add(service, ts, level, template_id, event.get("latency_ms"), event.get("event_id"))
                tracker.add(msg.topic(), msg.partition(), msg.offset(), aggregator.window_start(ts))
                watermark.update(msg.topic(), msg.partition(), ts)
                first_event = first_event if first_event is not None else ts.timestamp()
                events += 1
            if messages:
                last_message = time.monotonic()

            assigned = consumer.assignment()
            current = None
            if assigned and first_event is not None:
                caught_up = caught_up_partitions(consumer, assigned, next_offset)
                current = watermark.current([(tp.topic, tp.partition) for tp in assigned], caught_up)

            if current is not None:
                closed = aggregator.close_until(current - grace)
                complete = [w for w in closed if w.start_epoch >= first_event]
                if closed:
                    results, idle_minutes = judge_windows(detector, complete)
                    created = store.write(results, model["id"]) if results else []
                    if created:
                        publisher.publish(created, model)
                    windows_stored += len(results)
                    anomalies_created += len(created)
                    offsets = tracker.committable(aggregator.closed_before)
                    if offsets:
                        consumer.commit(offsets=offsets, asynchronous=False)

                    idle_set = set(idle_minutes)
                    for start in sorted({r.window.start for r in results} - idle_set):
                        minute = [r for r in results if r.window.start == start]
                        line = [f"{SHORT.get(r.window.service, r.window.service)} {r.window.log_count}"
                                + (f" [{r.severity}]" if r.is_anomaly else "") for r in minute]
                        print(f"  {start:%H:%M} UTC  " + " | ".join(line))
                        for r in minute:
                            if r.is_anomaly:
                                print(f"      ! {r.window.service} {r.severity} (score {r.score:.2f}): "
                                      + "; ".join(r.reasons))
                    if idle_minutes and not warned_idle:
                        print(f"  [WARN] no logs from any service since {idle_minutes[0]:%H:%M} UTC "
                              f"(no traffic); windows stored without anomalies")
                        warned_idle = True
                    if len(idle_set) < len({r.window.start for r in results}):
                        warned_idle = False

            if args.idle_exit is not None and time.monotonic() - last_message >= args.idle_exit:
                break
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()   # open windows are not committed: they are replayed after a restart

    print(f"\nEvents {events:,} (invalid {invalid}, late {aggregator.late_events}); windows stored {windows_stored}; "
          f"anomalies {anomalies_created} (published {publisher.delivered}, failed {publisher.failed}); "
          f"events in open windows (to be replayed): {tracker.pending}")
    return 0


if __name__ == "__main__":
    sys.exit(main())