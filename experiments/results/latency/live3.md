# Pipeline speed: live3

Periods (UTC): 2026-11-16 14:52–15:11. Database clock offset -0.00 s (subtracted where clocks are mixed).

| Stage | n | median | p95 | p99 | max |
|---|---|---|---|---|---|
| Log created → stored in Elasticsearch | 62,625 | 0.56 s | 1.04 s | 1.09 s | 1.14 s |
| Minute ends → anomaly stored | 21 | 6.10 s | 6.16 s | 6.17 s | 6.17 s |
| Anomaly → alert opened | 8 | 0.79 s | 1.04 s | 1.04 s | 1.05 s |
| Alert opened → Telegram message sent | 6 | 1.75 s | 13.60 s | 13.89 s | 13.97 s |
| Anomaly → shown on the dashboard (live feed) | 21 | 0.01 s | 0.04 s | 0.04 s | 0.04 s |
| Anomaly → new alert shown on the dashboard | 8 | 0.85 s | 1.10 s | 1.10 s | 1.10 s |

Alerts notified only later (escalation or retry, left out of the Telegram stage): 1.

| Incident | Fault start (UTC) | → first anomaly | → first alert | → first Telegram |
|---|---|---|---|---|
| silent_service | 14:56:04 | 60.6 s | 61.5 s | 62.5 s |
| cascading_failure | 15:04:30 | 35.5 s | 35.7 s | 97.4 s |
| **median** | | 48.0 s | 48.6 s | 80.0 s |
