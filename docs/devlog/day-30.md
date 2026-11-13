# Day 30 — Live feed /ws/live (Phase 7 complete)

## Done
- backend/api/app/realtime.py: LiveHub (fan-out to all browsers, bounded queue per browser) and AnomalyListener
  (background thread reading anomalies.detected, converting the Kafka format to the API anomaly item).
- routers/live.py: WebSocket /api/v1/ws/live; ping every 30 s.
- routers/alerts.py: PATCH /alerts/{id} pushes "alert.updated" after the change is committed.
- main.py: hub, listener and ping task in the lifespan; config.py: live_kafka_enabled, live_ping_s, live_queue_size.
- scripts/watch_live.py: prints the live feed in the terminal.
- tests: test_api_live.py (4, no Kafka), test_api_live_integration.py (1, real Kafka); 39 API tests pass.
- All 14 REST endpoints and the WebSocket of api-contracts.md 1.1 are implemented and tested.

## Decisions
- Every API instance must receive every anomaly. A consumer group divides partitions among members, so the
  listener assigns itself all partitions directly at the current end offset (group "api-group" used as a label
  only, no committed offsets). History comes from GET /anomalies.
- A browser whose queue (100 events) fills up is disconnected; the others are unaffected.
- The API starts without Kafka; the listener retries every 5 s.

## Live test (run-20261113-170122, error_burst from 17:02:22 UTC)
- Chain: generator -> Kafka -> detection -> PostgreSQL + anomalies.detected -> API -> WebSocket client.
- Received: payment CRITICAL 24.8% (window 17:02), CRITICAL 39.3% (17:03), HIGH 18.3% (17:04), gateway
  HIGH/HIGH/MEDIUM in the same minutes. First event on screen 44 s after fault start
  (window end + 5 s grace + ~1 s), at the same moment the detection service printed it.

## Finding: false alarms where traffic starts or stops mid-minute
- The detection service caught up on the 20-second test run of Day 29 (16:32:50–16:33:10). Both windows held
  only part of a minute of traffic and were flagged HIGH "log volume 15–19% of normal" (6 anomalies).
- Current rules handle fully empty minutes (no traffic) and the first window after start-up, not partial
  traffic at the start or end of a traffic period. Real traffic rarely starts/stops like this, but deployments
  or restarts could. Phase 10, together with the Day 26 volume-rule question.

## Notes
- The integration test publishes one marked message (reasons ["integration test"]) to anomalies.detected;
  the alerting service (Phase 8) must start from the end of the topic, not replay old messages.