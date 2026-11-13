# Day 31 — Alerting service: grouping anomalies into alerts

## Done
- backend/common/kafka_topics.py: ensure_topics (create missing topics, idempotent).
- backend/alerting/: config.py, rules.py (severity order, escalation, titles), store.py (grouping in one
  transaction per anomaly, row locks), service.py (anomalies.detected -> PostgreSQL alerts -> alerts.events).
- API: listener reads anomalies.detected and alerts.events and forwards alert.created / alert.updated to /ws/live
  (realtime.py FeedListener, config kafka_topic_alerts).
- tests: test_alerting_rules.py (3), test_alerting_integration.py (1, grouping/escalation/threshold/duplicate/
  unknown), test_api_live.py (+1); 44 API and alerting tests pass.
- Decision: notifications via Telegram only (email dropped; it adds SMTP setup without research value).

## Rules (with reasons)
- An anomaly joins an OPEN/ACKNOWLEDGED alert of the same service within 5 minutes; otherwise a new alert opens
  (consecutive bad minutes are one incident; edge minutes are sometimes not flagged, Day 26).
- A LOW anomaly never opens an alert, but can join one (the only fault-free false alarm was LOW, Day 25).
- Alert severity = highest seen; message = latest reasons; title from the strongest reason.
- Re-processing an anomaly changes nothing (already linked): safe with Kafka's at-least-once delivery.
- New consumer group starts at the end of anomalies.detected; offsets committed after storing and publishing.
- alerts.events is created by the service/API on start-up (move into kafka-init in Phase 10).

## Live run (run-20261113-174638, error_burst from 17:47:38 UTC)
- payment-service: 3 anomalies -> 1 alert "Error rate increase in payment-service", HIGH -> CRITICAL, x3.
- api-gateway: 3 anomalies -> 1 alert, MEDIUM -> HIGH, x3.
- auth-service LOW anomaly at 17:48 (healthy service, false alarm) -> "no alert, below MEDIUM".
- /ws/live showed anomaly.created followed ~1 s later by alert.created / alert.updated.
- GET /alerts: 2 OPEN alerts, occurrence_count 3, notification_sent false.

## Observations
- The gateway alert is a symptom of the payment fault. Linking such alerts (root-cause correlation across
  services, e.g. via trace_id) is future work.
- The integration test's marked message appeared in a running API's live feed (expected; no alert created).