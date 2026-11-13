# Day 28 — Anomaly and log endpoints

## Done
- backend/api/app/params.py: shared query parameters (from/to default last hour, page/size max 200,
  comma-separated value lists with 400 for unknown values).
- backend/api/app/es_queries.py: log lookup by id (mapping-independent), removal of the internal ingested_at.
- routers/anomalies.py: GET /anomalies (service, severity, feedback incl. NONE, time range, pagination),
  GET /anomalies/{id} (sample logs from Elasticsearch in stored order, missing omitted, sample_logs_error if
  Elasticsearch is down), PATCH /anomalies/{id}/feedback (set or clear, feedback_at recorded).
- routers/logs.py: GET /logs (full-text q, service, level, trace_id, time range, newest first, total, 10,000
  result-window limit), GET /logs/{event_id}.
- main.py: 503 "Elasticsearch unavailable" handler.
- tests: test_api_health.py (4), test_api_anomalies_integration.py (9), test_api_logs_integration.py (6);
  23 API tests pass. Integration tests create their own data on 2001-01-01/02 and remove it afterwards.

## Decisions
- Log queries follow the actual index template (checked before writing them): keyword fields (service, level,
  trace_id) -> exact term filters; message (text) -> full-text match with all words required; timestamp (date)
  -> range and sort, event_id as tie-breaker.
- Anomaly detail returns the anomaly even when Elasticsearch is down (contract 1.1).
- Feedback is the first write endpoint: labelled operator feedback for future model work (drift).

## Live check on real data (2026-11-13)
- /anomalies?severity=CRITICAL: 8 anomalies with reasons.
- /anomalies/{id} for api-gateway 12:09 (silent auth): 10 sample logs, all "503 ... auth-service unavailable
  (connection refused)", matching the reasons "error rate 32.1%; 2 new message type(s)".
- /logs level=ERROR: 2,578 today; q=timeout: 288 (inventory lock, database write and query timeouts).

## Problems faced
- PATCH feedback failed: "inconsistent types deduced for parameter $1 — text versus character varying". The same
  parameter was used as a VARCHAR value and in a ::text IS NULL test. Fixed with a separate boolean parameter.
- One test (default time range) passed without checking anything meaningful; rewritten to assert that the 2001
  test anomalies are not in the last hour.

## Findings
- The log generator writes timestamps with six decimals ("12:11:53.074000Z"); contracts.md §1 requires
  millisecond precision. Ingestion accepts it (valid ISO 8601). Fix at the source on Day 29.