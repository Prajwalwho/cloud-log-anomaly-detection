# Day 11 — Phase 4 wrap-up: latency, end-to-end test, documentation

## Done
- scripts/pipeline_latency.py: pipeline latency (ingested_at − timestamp) computed in Elasticsearch with a
  runtime field; min/avg/max, p50/p95/p99, p95 per service; warns about backlog windows.
- tests/integration/test_pipeline_integration.py: end-to-end test generator -> Kafka -> ingestion ->
  Elasticsearch (counts, trace reconstruction, ingested_at present), using temporary topics and indices.
- docs/design/elasticsearch-design.md: index naming, template, mappings, idempotency, writing, queries.
- docs/architecture/system-architecture.md v2.0: rewritten to match the implementation; each component
  marked Implemented/Planned; delivery guarantees, evaluation method and limitations added.
- README.md: pipeline usage, tools, tests, updated roadmap (Phases 0–4 done).
- Phase 4 (ingestion) complete.

## Results
- Tests: 54 passed (45 unit, 9 integration).
- Live run: 120 s, 8,461 events generated, 8,461 delivered to Kafka, 8,461 stored in Elasticsearch, 0 invalid.
  Consumer kept pace with the generator (~70 events/s); 112 batches committed.

| Pipeline latency (timestamp -> stored) | ms |
|---|---|
| min | 2 |
| average | 570 |
| p50 | 570 |
| p95 | 1,065 |
| p99 | 1,111 |
| max | 1,142 |

- p95 per service: 1,059–1,074 ms (identical across services).
- Logs are searchable up to 5 s after storage (refresh_interval): worst case ~6 s from creation to search.

## Observations
- Latency is dominated by batching. The consumer requests up to 500 messages and waits at most 1 s;
  at ~70 events/s a batch never fills, so it waits the full second (112 batches in 120 s, ~75 events each).
  Latencies are therefore spread evenly between ~0 and ~1.1 s (median ≈ half the wait).
- Same p95 for every service confirms the delay comes from batching, not from any service or partition.
- Latency vs throughput trade-off, measured on both sides:
  - live: median 570 ms at ~70 events/s;
  - backlog (Day 10): ~3,300 events/s, because batches fill instantly.
  Lowering ingestion_poll_timeout_s (e.g. to 0.2 s) would reduce median latency to ~100 ms at the cost of
  ~5x more batches and offset commits. Not needed: detection uses 60-second windows, so ~1 s is negligible.

## Problems faced
- None.