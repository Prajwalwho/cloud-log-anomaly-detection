# Day 2 — Database design and API contracts

## Done
- docs/design/database-design.md: 5 tables (services, model_registry, detection_windows, anomalies, alerts), relationships, indexes, write ownership.
- infrastructure/docker/postgres/init.sql: full schema with constraints, indexes and seed services.
- docs/design/api-contracts.md: 14 REST endpoints and the /ws/live WebSocket protocol.

## Decisions
- Every scored window is stored (not only anomalies), so trend charts and live evaluation are possible.
- Multiple anomalies of one service are grouped into one alert (deduplication).
- Each table has a single writer service.
- Administrators can mark anomalies as false positives (feedback column).
- Dashboard statistics are served from PostgreSQL, not Elasticsearch.
- Authentication is out of scope for now.

## Problems faced
- None (init.sql will be tested on Day 3 when Postgres runs).