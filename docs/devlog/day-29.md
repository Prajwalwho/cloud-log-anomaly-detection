# Day 29 — Statistics and alert endpoints; ingestion timestamp fix

## Done
- routers/stats.py: GET /stats/summary (totals, error rate, anomalies by severity and service, open alerts) and
  GET /stats/timeseries (log_count, error_rate, avg_latency_ms, anomaly_score, anomaly_count; buckets 1m/5m/1h
  with date_bin; max 2,000 points per series), both from detection_windows.
- routers/alerts.py: GET /alerts (status, severity, service, time range on last_seen_at), GET /alerts/{id}
  (with its anomalies), PATCH /alerts/{id} with the contract's transitions (row locked during the change).
- schemas.py: alert, summary and timeseries models.
- es_queries.py: log timestamps normalised to ms precision in API responses (covers documents stored before the fix).
- backend/ingestion/es_sink.py: documents store the timestamp in the contract format.
- tests: test_api_es_queries.py (3), test_es_sink_timestamp.py (4), test_api_stats_alerts_integration.py (8);
  34 API tests and 140 unit tests pass.
- 13 of 14 endpoints done; /ws/live remains (Day 30).

## Live check (Day 26 run, 11:50–12:20 UTC)
- /stats/summary: 64,440 logs, 90 windows, 23 anomalies (4 MEDIUM, 11 HIGH, 8 CRITICAL), matching the 23 anomalies
  the detection service stored and published; api-gateway leads (10 anomalies, 8.9% error rate).
- /stats/timeseries error_rate, payment-service, 1m: 0.3% (11:54) -> 16.8% -> 42.2% -> 22.9% (11:55–11:57) ->
  0.7% (11:58) -> ~0: the error burst exactly.

## Correction to day 28
- Day 28 attributed six-decimal timestamps ("…53.074000Z") to the log generator. Reading the code showed the
  generator already writes milliseconds (format_timestamp). The cause was ingestion: es_sink.to_document used
  model_dump(mode="json"), which writes Pydantic datetimes with microseconds. Fixed in es_sink; new documents store
  "…53.074Z" (verified: 2026-11-13T16:33:10.141Z). Lesson: read the code before naming the cause.

## Decisions
- Statistics assume one model scored each period (always the case here); two models on the same period would be
  counted twice.
- Time series are capped at 2,000 points per series (400 otherwise), so the dashboard never receives huge responses.

## Notes
- uvicorn --reload watches the whole project; use --reload-dir backend/api.