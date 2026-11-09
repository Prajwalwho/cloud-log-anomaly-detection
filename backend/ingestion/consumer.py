"""
Ingestion service: consumes log events from Kafka, validates them against the contract,
stores valid events in a sink (Elasticsearch), and sends invalid messages to the
dead-letter topic.

Delivery guarantee: at-least-once. Offsets are committed only after a whole batch has
been written to the sink and every dead-letter message is confirmed by Kafka. A crash
can therefore cause a batch to be processed twice, but never lost. The Elasticsearch
sink uses event_id as the document id, so processing twice is harmless.

Usage (run from the project root):
    python -m backend.ingestion.consumer
    python -m backend.ingestion.consumer --idle-exit 10
    python -m backend.ingestion.consumer --group reindex-test --idle-exit 15
    python -m backend.ingestion.consumer --sink counting
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from confluent_kafka import Consumer, KafkaError, Message, Producer

from .config import IngestionSettings
from .config import settings as default_settings
from .es_sink import ElasticsearchSink
from .kafka_client import create_consumer, create_producer, require_topics
from .validator import LogEvent, build_deadletter_record, describe_error, validate_message

STATS_INTERVAL_S = 5.0


class EventSink(Protocol):
    """Destination for validated events. Returns events it rejected permanently, with reasons."""

    def write_batch(self, events: list[LogEvent]) -> list[tuple[LogEvent, str]] | None: ...


class CountingSink:
    """Sink without storage: counts events per service (for testing without Elasticsearch)."""

    def __init__(self) -> None:
        self.by_service: Counter = Counter()

    def write_batch(self, events: list[LogEvent]) -> list[tuple[LogEvent, str]]:
        for event in events:
            self.by_service[event.service] += 1
        return []


@dataclass
class IngestionStats:
    received: int = 0
    valid: int = 0          # validated AND stored
    invalid: int = 0        # sent to the dead-letter topic
    batches: int = 0
    rejected_fields: Counter = field(default_factory=Counter)


class IngestionConsumer:
    def __init__(
        self,
        sink: EventSink,
        config: IngestionSettings = default_settings,
        consumer: Consumer | None = None,
        producer: Producer | None = None,
    ) -> None:
        self.config = config
        self.sink = sink
        self.consumer = consumer or create_consumer(config.kafka_bootstrap_servers, config.ingestion_group_id)
        self.producer = producer or create_producer(config.kafka_bootstrap_servers, "ingestion-deadletter")
        self.stats = IngestionStats()
        self._deadletter_failures = 0

    # ---------------- main loop ----------------
    def run(self, idle_exit_s: float | None = None, verbose: bool = True) -> IngestionStats:
        """Consume until Ctrl+C, or until no messages arrive for idle_exit_s seconds."""
        require_topics(self.consumer, [self.config.kafka_topic_logs, self.config.kafka_topic_deadletter])
        self.consumer.subscribe([self.config.kafka_topic_logs])

        last_message = last_report = time.monotonic()
        last_received = 0
        try:
            while True:
                messages = self.consumer.consume(
                    num_messages=self.config.ingestion_batch_size,
                    timeout=self.config.ingestion_poll_timeout_s,
                )
                now = time.monotonic()
                if messages:
                    self.process_batch(messages)
                    last_message = now
                elif idle_exit_s is not None and now - last_message >= idle_exit_s:
                    break

                if verbose and now - last_report >= STATS_INTERVAL_S:
                    rate = (self.stats.received - last_received) / (now - last_report)
                    print(f"  received {self.stats.received:>8} ({rate:6.0f}/s)   "
                          f"stored {self.stats.valid:>8}   invalid {self.stats.invalid:>5}")
                    last_report, last_received = now, self.stats.received
        except KeyboardInterrupt:
            pass
        finally:
            self.producer.flush(10)
            self.consumer.close()   # no commit here: only fully processed batches are committed
        return self.stats

    # ---------------- one batch ----------------
    def process_batch(self, messages: list[Message]) -> None:
        valid: list[tuple[LogEvent, Message]] = []
        processed = 0

        for msg in messages:
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"  consumer error: {msg.error()}", file=sys.stderr)
                continue
            processed += 1
            self.stats.received += 1
            try:
                valid.append((validate_message(msg.value()), msg))
            except Exception as exc:   # any contract violation goes to the dead-letter topic
                self._send_to_deadletter(msg, describe_error(exc))

        if not processed:
            return

        # 1. Store valid events (raises if the sink is unavailable -> batch is not committed)
        stored = 0
        if valid:
            rejected = self.sink.write_batch([event for event, _ in valid]) or []
            if rejected:
                source = {str(event.event_id): msg for event, msg in valid}
                for event, reason in rejected:
                    self._send_to_deadletter(source[str(event.event_id)], reason)
            stored = len(valid) - len(rejected)

        # 2. Dead-letter messages must be stored before the offsets move past them
        undelivered = self.producer.flush(10)
        if undelivered or self._deadletter_failures:
            raise RuntimeError("Dead-letter messages could not be delivered; offsets not committed")

        # 3. Only now mark the batch as done
        self.consumer.commit(asynchronous=False)
        self.stats.valid += stored
        self.stats.batches += 1

    def _send_to_deadletter(self, msg: Message, error: str) -> None:
        record = build_deadletter_record(msg.value(), msg.topic(), msg.partition(), msg.offset(), error)
        self.producer.produce(
            self.config.kafka_topic_deadletter,
            value=json.dumps(record).encode("utf-8"),
            on_delivery=self._on_deadletter_delivery,
        )
        self.producer.poll(0)
        self.stats.invalid += 1
        self.stats.rejected_fields[error.split(":", 1)[0]] += 1

    def _on_deadletter_delivery(self, err: KafkaError | None, msg: Message) -> None:
        if err is not None:
            self._deadletter_failures += 1
            print(f"  dead-letter delivery failed: {err}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingestion service: Kafka -> validation -> Elasticsearch.")
    parser.add_argument("--idle-exit", type=float,
                        help="stop after this many seconds without messages (default: run until Ctrl+C)")
    parser.add_argument("--group", help="consumer group id (default from settings: ingestion-group)")
    parser.add_argument("--sink", choices=["elasticsearch", "counting"], default="elasticsearch",
                        help="where valid events go (default: %(default)s)")
    args = parser.parse_args(argv)

    config = default_settings
    if args.group:
        config = default_settings.model_copy(update={"ingestion_group_id": args.group})

    if args.sink == "elasticsearch":
        sink: EventSink = ElasticsearchSink(config.elasticsearch_url, config.elasticsearch_index_prefix)
        try:
            sink.ensure_ready()
        except RuntimeError as exc:
            print(f"[FAIL] {exc}", file=sys.stderr)
            return 1
        destination = f"Elasticsearch {config.elasticsearch_url} (indices {config.elasticsearch_index_prefix}-*)"
    else:
        sink = CountingSink()
        destination = "counting sink (no storage)"

    service = IngestionConsumer(sink, config)
    print(f"Ingestion consuming '{config.kafka_topic_logs}' as group '{config.ingestion_group_id}'\n"
          f"  -> {destination}\n"
          f"  -> dead-letter: '{config.kafka_topic_deadletter}'\n"
          f"Press Ctrl+C to stop.")

    try:
        stats = service.run(idle_exit_s=args.idle_exit)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print(f"\nReceived {stats.received}, stored {stats.valid}, invalid {stats.invalid}, "
          f"batches committed {stats.batches}")
    if stats.rejected_fields:
        print("Rejected because of:")
        for field_name, count in stats.rejected_fields.most_common():
            print(f"  {field_name:<20} {count}")
    if isinstance(sink, ElasticsearchSink) and sink.indexed_by_index:
        print("Indexed per index:")
        for index, count in sorted(sink.indexed_by_index.items()):
            print(f"  {index:<20} {count}")
    if isinstance(sink, CountingSink) and sink.by_service:
        print("Valid events per service:")
        for service_name, count in sorted(sink.by_service.items()):
            print(f"  {service_name:<20} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())