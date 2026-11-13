# Day 27 — Backend API foundation (Phase 7 starts)

## Done
- Contracts aligned before building (separate commit): contracts.md 1.1 and api-contracts.md 1.1.
  - anomalies.detected: the Day 25 publisher sent a nested "model" object and non-millisecond timestamps,
    violating contracts.md §5.3; fixed in code (flat model_name/model_version, optional model_id, ms timestamps).
    test_publisher.py now checks the message against the contract field list.
  - Documented the summary fields added in Phase 6 (reasons, rule, raw_score, threshold, warn_rate, p95).
  - Defined the response formats of five endpoints the contract had left open (/services, /logs/{event_id},
    /alerts/{id}, /models, /models/active), the WebSocket conversion from the Kafka format, timeseries
    aggregation rules, and anomaly-detail behaviour when Elasticsearch is down.
- backend/api/app: config.py, timeutil.py, schemas.py, main.py (app factory, lifespan, CORS, 503 handler),
  routers/health.py, routers/services.py, routers/models.py.
- backend/api/requirements.txt: fastapi, uvicorn, psycopg pool, elasticsearch, confluent-kafka, httpx.
- Removed 15 empty placeholder files from the Day 0 structure (routes/, schemas/, services/, utils/,
  dependencies.py).
- tests: tests/unit/test_api_health.py (2, no Docker), tests/integration/test_api_integration.py (4).

## Design
- Sync endpoints (psycopg and the Elasticsearch client are sync; FastAPI runs them in a thread pool).
- PostgreSQL connection pool opened without waiting: the API starts even when the database is down.
- Dependency failures return 503 {"detail": ...} in the contract error format.
- Timestamps serialised as ISO 8601 UTC with milliseconds and Z.

## Results
- All 6 API tests pass; with every dependency unreachable the API still starts and /health returns 503
  "degraded" with all components "down".
- Live check: /health ok -> Elasticsearch stopped -> 503 degraded (elasticsearch down, postgres/kafka ok) ->
  Elasticsearch started -> ok again without restarting the API.
- /services returns the 5 seeded services; /models/active returns live-pca 1.1.0 with its training
  configuration and evaluation metrics.

## Problems faced
- ImportError "cannot import name 'HealthOut'": an empty placeholder package backend/api/app/schemas/ shadowed
  the new schemas.py (a package wins over a module of the same name). Removed all empty placeholders after
  checking that every one was 0 bytes.
- Clipboard: Set-Clipboard copies silently and each call overwrites the previous one; files pasted one per
  message. Get-Content shows UTF-8 characters wrongly in Windows PowerShell unless -Encoding UTF8 is given
  (display only, files are fine).
- Test warning "Using httpx with starlette.testclient is deprecated; install httpx2": not acted on yet; the
  suggested package must be verified before installing.