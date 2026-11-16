# Day 42 — Load test

## Built
- `scripts/load_test.py`: runs the generator at several rates back to back (default 20 / 50 / 100 / 200 requests/s,
  5 min each), samples the ingestion lag every 5 s and `docker stats` once per step, waits for ingestion to drain,
  then measures each step: ingestion latency (Elasticsearch), minute end → judged (detection_windows), flagged
  windows, verdict. Output: `experiments/results/load/<label>.json` / `.md`.
- `backend/detection/evaluation/load.py`: generator output parsing, lag trend, stall check, keep-up verdict;
  11 unit tests.
- `latency_report.ingest_latency(..., backlog_ms=None)` keeps every log (the load test must see slow ones).
- Alerting: `--no-telegram` switch.
- The load test stops after ~90 s if ingestion is not consuming.

## Runs
- l1: ingestion had stopped at start-up (Elasticsearch still starting) → no logs stored; detection valid.
- l2: everything up, but two detection and two alerting services were running (left over from l1) → ingestion
  valid, detection's flagged windows not.
- Results (docs/testing/load-test-results.md): at 200 requests/s (735 events/s, 10× normal) ingestion p95 0.71 s,
  max lag 582 events; detection judged every minute ≤ 6.2 s after it ended; 407,128 events, 0 failed.
- At 5× and 10× traffic the model flags minutes as LOW (trained at 1×); no alerts.

## Problems and lessons
- Start the services only after `start.ps1 up` reports all containers healthy.
- PowerShell: `$env:X=""` deletes the variable instead of emptying it, so .env was used again (Telegram stayed on).
  Replaced by `--no-telegram`.
- Two detection processes in one group split the partitions; each judged the services it could not see as silent
  (false "stopped logging" CRITICAL alerts). Guard planned for Day 43.
- Check for leftover services: `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` (each service appears as
  two processes on Windows: venv launcher + interpreter).

## Next
- Day 43: improvements (detection partition guard, Telegram in the background, partial-minute false alarms,
  random scenario start offset).