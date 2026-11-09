# Day 8 — Publishing logs to Kafka

## Done
- backend/log_generator/producer.py: KafkaLogPublisher (keyed by service, delivery callbacks,
  connection and topic check before publishing, handling of a full local send queue).
- generator.py: --kafka option; progress output; delivery summary; exit code 1 if any event was not delivered.
- scripts/kafka_peek.py: reads a topic and verifies message format, key = service, and that each service
  always maps to one partition.
- tests/integration/test_kafka_publish.py: first integration tests (round trip through a temporary topic,
  clear error for a missing topic). Skipped automatically when Kafka is not running.
- pyproject.toml: `integration` test marker.
- Removed placeholder backend/ingestion/producer.py: producing logs belongs to the generator;
  ingestion only consumes.
- Phase 3 (log generator) complete.

## Design decisions
- Key = service: guarantees per-service ordering (needed for windowing). Trade-off: with 5 services and
  3 partitions the load per partition is uneven.
- acks=all + idempotence: no lost or duplicated messages from producer retries.
- linger.ms=20 + lz4 compression: batching for throughput.
- murmur2 partitioner: same key-to-partition mapping as Kafka's Java clients.
- Fail fast: the generator checks Kafka and the topic before generating anything.

## Results
- (paste: delivered/failed counts from the 30 s run, and the kafka_peek partition summary)

## Problems faced
- (note anything you hit)