# Pipeline speed: live1

Periods (UTC): 2026-11-16 07:13–07:39. Database clock offset +0.00 s (subtracted where clocks are mixed).

| Stage | n | median | p95 | p99 | max |
|---|---|---|---|---|---|
| Log created → stored in Elasticsearch | 92,140 | 0.61 s | 1.09 s | 1.15 s | 1.60 s |
| Minute ends → anomaly stored | 18 | 5.87 s | 6.37 s | 6.39 s | 6.40 s |
| Anomaly → alert opened | 8 | 0.66 s | 1.54 s | 1.77 s | 1.83 s |
| Alert opened → Telegram message sent | 5 | 0.97 s | 1.48 s | 1.57 s | 1.59 s |
| Anomaly → shown on the dashboard (live feed) | 18 | 0.06 s | 0.07 s | 0.09 s | 0.09 s |
| Anomaly → new alert shown on the dashboard | 8 | 1.33 s | 2.70 s | 2.82 s | 2.85 s |

Alerts notified only later (escalation or retry, left out of the Telegram stage): 3.

| Incident | Fault start (UTC) | → first anomaly | → first alert | → first Telegram |
|---|---|---|---|---|
| error_burst | 07:17:37 | 28.5 s | 29.2 s | 30.9 s |
| new_error | 07:25:37 | 28.5 s | 29.1 s | — |
| silent_service | 07:33:37 | 27.8 s | 28.3 s | 29.3 s |
| **median** | | 28.5 s | 29.1 s | 30.1 s |
