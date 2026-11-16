# Day 41 — Pipeline speed

## Built
- `backend/detection/evaluation/latency.py`: stage durations, percentiles, per-incident chain (fault → first
  anomaly → first alert → first Telegram), live-feed records; pure functions, 7 unit tests
  (`tests/unit/test_latency_metrics.py`).
- `scripts/latency_report.py`:
  - `watch` records the dashboard's live feed (/ws/live) with receive times;
  - `report` combines Elasticsearch (ingested_at − timestamp, percentiles computed by Elasticsearch), PostgreSQL
    (anomalies, alerts) and the recorded feed into `experiments/results/latency/<label>.json` and `.md`.
  - Measures the offset between the database clock (Docker) and the laptop clock and subtracts it where both are
    mixed; logs over 60 s old (backlog) are counted, not mixed in.
- Alerting: `notified_at` now keeps the time of the FIRST Telegram message; before, an escalation overwrote it.

## Run live1 (16 Nov, 07:13–07:42 UTC)
- 3 faults, 98,179 events, all services live. Results: docs/testing/latency-results.md.
- Log → Elasticsearch 0.61 s median (p95 1.09 s); minute end → anomaly 5.87 s (5 s grace); anomaly → dashboard
  0.06 s; anomaly → alert 0.66 s; alert → Telegram 0.97 s.
- Fault → Telegram 29–31 s (faults at second :37 of the minute); matches "rest of the minute + ≈ 7.5 s".
- Finding: Telegram sends are made in line, so in a multi-service failure each later alert waits ≈ 0.9 s per earlier
  message (silent_service: 1.0 / 1.9 / 2.9 s). Fix planned for Day 43 (background sender).
- Alerts that open as MEDIUM are notified only when they reach HIGH (new_error: ≈ 90 s); by design.

## Problems
- First attempt: Docker was not running, every service stopped with "not reachable"; nothing was written.
- The test file was first saved as `test_latency_matrics.py`; renamed.

## Next
- Day 42: load test (20 / 50 / 100 / 200 events per second).