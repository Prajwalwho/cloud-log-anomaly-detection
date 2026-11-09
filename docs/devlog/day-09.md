# Day 9 — Ingestion consumer with validation and dead-letter

## Done
- backend/ingestion/config.py: ingestion settings (topics, consumer group, batch size).
- backend/ingestion/validator.py: LogEvent Pydantic model implementing the contract (Section 2.4):
  strict types, allowed levels, UTC timestamps not >5 min in the future, value ranges, no extra fields.
  Readable error descriptions and dead-letter records (Section 5.2).
- backend/ingestion/kafka_client.py: consumer/producer factories, topic check.
- backend/ingestion/consumer.py: batch consumer (up to 500 messages), validation, dead-letter publishing,
  manual offset commits, live statistics, graceful Ctrl+C.
- scripts/send_invalid_logs.py: one broken message per validation rule plus a valid control message.
- tests/unit/test_validator.py (24 tests) and tests/integration/test_ingestion.py (1 test).

## Design decisions
- At-least-once delivery: offsets are committed only after the sink write AND dead-letter delivery succeed.
  A crash can reprocess a batch but never lose one. Reprocessing will be made harmless on Day 10 by using
  event_id as the Elasticsearch document id (idempotent writes).
- Strict validation: "500" is rejected for status_code; the contract says integer.
- Invalid messages are never dropped: the original text and the reason go to logs.deadletter.
- auto.offset.reset=earliest: a new consumer group starts with the oldest retained message (no data loss).
- Sink is an interface (write_batch): counting sink today, Elasticsearch tomorrow, without changing the consumer.

## Results
- Tests: 47 passed (44 unit, 3 integration).
- Live run: generator sent 1,859 events (30 s) + 11 validation-test messages.

| Metric | Value |
|---|---|
| Received | 1,870 |
| Valid | 1,860 (1,859 generator + 1 control) |
| Invalid (dead-letter) | 10 |
| Batches committed | 31 |
| Consumer throughput | ~65 messages/s (matched the generator rate; no backlog) |
| Consumer lag after run | 0 on all 3 partitions |

- Rejections by field: level 2 (missing, unknown value), status_code 2 (string, out of range),
  json 1, timestamp 1, extra field "user" 1, latency_ms 1, schema_version 1, message 1.
- Dead-letter records contain the reason, source partition/offset and the original message text.
- Restarting the consumer received 0 messages: committed offsets were respected (resume, not reprocess).

## Problems faced
- Docker Desktop was not running after a laptop restart; the scripts and integration tests reported this
  clearly (integration tests were skipped, not failed). Daily routine: start Docker Desktop, then start.ps1 up.
- Ran two commands as one line ("... --duration 30, then python ..."); run commands one at a time.