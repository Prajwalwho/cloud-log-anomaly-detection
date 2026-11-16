# Day 46 — Docs: Using the dashboard, Alerts and Telegram, Operations

## Written
- `docs/guide/using-the-dashboard.md`: what is on every page (sidebar signals, time range, local time, addresses
  that keep filters); Overview (the galaxy and its colours, the readout, the three charts and their time steps, live
  signals); Anomalies (filters, list, the detail sections, verdicts); Alerts (filters, list, what happened, the
  story, Telegram, respond); Logs (search, filters, Refresh, limits, line details, following a request by trace ID);
  Models; Docs.
- `docs/guide/alerts-and-telegram.md`: how an anomaly joins an alert or opens one (5-minute gap, MEDIUM minimum,
  repeats ignored), titles, the life of an alert (open, acknowledged, resolved; automatic resolution after 5 quiet
  minutes), Telegram rules (new at HIGH, escalated to CRITICAL, resolved; at most three per alert) with the real
  message format, background sending and retries, setup with @BotFather and `telegram_setup.py`, turning Telegram
  off, the settings with their defaults, acknowledging and resolving by dashboard or API.
- `docs/guide/operations.md`: `start.ps1` actions, start order of the services and why, finding and stopping
  processes, one copy per service, health checks, consumer lag and skipping old messages, laptop runs, disk space
  (Elasticsearch daily indices, Kafka retention, compacting Docker's virtual disk), retraining, tests, the
  measurement scripts, troubleshooting.
- The docs sidebar gets a **Use** section; the guide's README lists the new pages.

## Checked against the code and data
- Filter and button labels (dashboard pages and components); settings and defaults (`alerting/config.py`); titles
  (`alerting/rules.py`); message format and icons (`alerting/notifier.py`); notification rules and the start-up line
  (`alerting/service.py`): an alert resolved by an operator sends no Telegram message; PATCH body
  (`api/app/schemas.py`); `start.ps1` actions; Kafka retention and no Kafka volume (`docker-compose.yml`); daily index
  names (`ingestion/config.py`); script options (`live_eval.py`, `latency_report.py`, `load_test.py`, generator
  `--jitter`); resolve times 5.1–6.4 min and 2.5 alerts per incident (live-evaluation-results.md); the 14-s send
  (improvements-results.md).

## Next
- Day 47: architecture, API reference, configuration, glossary and FAQ; README update.
- Day 48: study guide and final check.