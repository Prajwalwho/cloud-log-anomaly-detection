# Pipeline speed: night

Periods (UTC): 2026-11-14 19:18–19:57; 2026-11-14 19:59–20:38; 2026-11-14 21:35–22:14; 2026-11-14 22:17–23:14. Database clock offset +0.01 s (subtracted where clocks are mixed).

| Stage | n | median | p95 | p99 | max |
|---|---|---|---|---|---|
| Log created → stored in Elasticsearch | — | — | — | — | — |
| Minute ends → anomaly stored | 102 | 5.92 s | 6.28 s | 6.53 s | 6.54 s |
| Anomaly → alert opened | 38 | 1.06 s | 12.43 s | 13.37 s | 13.62 s |
| Alert opened → Telegram message sent | 26 | 0.89 s | 8.48 s | 10.93 s | 10.93 s |
| Anomaly → shown on the dashboard (live feed) | — | — | — | — | — |
| Anomaly → new alert shown on the dashboard | — | — | — | — | — |

Alerts notified only later (escalation or retry, left out of the Telegram stage): 10.

| Incident | Fault start (UTC) | → first anomaly | → first alert | → first Telegram |
|---|---|---|---|---|
| error_burst | 19:22:09 | 56.6 s | 56.8 s | 58.0 s |
| latency_spike | 19:29:09 | 56.8 s | 57.4 s | 58.2 s |
| new_error | 19:36:09 | 56.6 s | 57.0 s | 57.9 s |
| silent_service | 19:43:09 | 56.8 s | 57.4 s | 58.3 s |
| cascading_failure | 19:50:09 | 56.7 s | 57.7 s | 128.1 s |
| latency_spike | 20:03:09 | 55.8 s | 56.0 s | 57.0 s |
| new_error | 20:10:09 | 55.6 s | 56.7 s | 58.5 s |
| silent_service | 20:17:09 | 55.5 s | 57.0 s | 128.6 s |
| cascading_failure | 20:24:09 | 55.8 s | 56.2 s | 118.0 s |
| error_burst | 20:32:09 | 55.9 s | 56.8 s | 57.7 s |
| new_error | 21:39:57 | 7.9 s | 8.7 s | 69.2 s |
| silent_service | 21:46:57 | 9.1 s | 9.4 s | 70.4 s |
| cascading_failure | 21:53:57 | 68.6 s | 69.5 s | 130.0 s |
| error_burst | 22:01:57 | 68.6 s | 69.2 s | 70.0 s |
| latency_spike | 22:08:57 | 68.0 s | 68.7 s | 69.5 s |
| **median** | | 56.6 s | 57.0 s | 69.2 s |
