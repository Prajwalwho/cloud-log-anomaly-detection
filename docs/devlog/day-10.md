# Day 10 — Indexing logs into Elasticsearch

## Done
- backend/ingestion/es_sink.py: ElasticsearchSink with index template, daily indices, bulk indexing,
  idempotent writes (event_id as document id), retry with backoff, permanent rejections returned.
- backend/ingestion/consumer.py: Elasticsearch as default sink (--sink counting still available);
  documents rejected by Elasticsearch go to the dead-letter topic.
- backend/ingestion/config.py: elasticsearch_index_prefix.
- scripts/search_logs.py: search by service, level, text, time window, and full request trace.
- tests/unit/test_es_sink.py (4 tests), tests/integration/test_es_sink_integration.py (2 tests).
- Full pipeline working: generator -> Kafka -> ingestion -> Elasticsearch.

## Design decisions
- Daily indices (logs-YYYY.MM.DD by event UTC time): old data is deleted per day, cheaply.
- Index template: explicit types (keyword for exact filters/aggregations, text for message search,
  date, integer, float, flattened metadata), 1 shard, 0 replicas (single node -> green cluster),
  strict mapping, refresh every 5 s (near real-time search). Priority 500 (see problems).
- Idempotent writes: document id = event_id. Together with at-least-once delivery from Kafka this gives
  effectively-once storage: no lost logs and no duplicates.
- ingested_at stored per document, so pipeline latency (ingested_at - timestamp) can be measured.
- Transient Elasticsearch failures: 5 attempts with exponential backoff (1, 2, 4, 8 s); if still failing,
  the consumer stops without committing, and resumes from Kafka after restart.

## Results
- Tests: 53 passed (45 unit, 8 integration).
- Live run: error_burst scenario (60 s normal, 120 s fault, 60 s normal), 18,190 events.
- Backlog recovery: the consumer was down during the run; all 18,190 events waited in Kafka and were
  ingested afterwards at ~3,300 events/s (about 50x the live rate). 0 lost.
- Search results (last 60 min):
  - ERROR logs: 546 = payment-service 253 (fault) + api-gateway 273 (502s caused by the fault)
    + 20 baseline errors in other services.
  - Full-text "card processor timeout": exactly the 253 payment failures.
- Trace e821745fef6cbaf2 (one checkout) reconstructed across 5 services in order:
  auth 11 ms -> order 38 ms -> inventory 11 ms -> payment 81 ms -> gateway 201 in 143 ms
  (gateway total = sum of steps + routing overhead).
- Idempotency demo (fresh consumer group re-reading the whole topic):

| | Documents |
|---|---|
| Before reprocessing | 18,190 |
| After reprocessing | 20,050 |
| Expected if duplicated | 38,240 |

  The 18,190 existing logs were rewritten without duplicates; the 1,860 added are the morning's Day 9 logs,
  which had gone to the counting sink and were stored for the first time. The 10 invalid test messages
  were sent to the dead-letter topic again.

## Problems faced
- pytest "import file mismatch": tests/unit/test_es_sink.py and tests/integration/test_es_sink.py had the
  same file name, which pytest does not allow without packages. Renamed the integration test to
  test_es_sink_integration.py. Convention from now on: integration test files end in _integration.py.
- Consumer failed at startup: Elasticsearch 8 has a built-in index template "logs" (pattern logs-*-*,
  priority 100) that overlaps our logs-* pattern at the same priority. Fixed by giving our template
  priority 500. Our index names (logs-YYYY.MM.DD) never match logs-*-*.
- search_logs.py crashed with KeyError 'aggregations' when no indices existed: Elasticsearch omits
  aggregations for empty results. Fixed to handle empty results.
- No data was lost while the consumer was down: the events stayed in Kafka (24 h retention) and were
  ingested as a backlog once the consumer started. This demonstrates the decoupling Kafka provides.