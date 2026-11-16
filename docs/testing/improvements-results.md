# Improvements after the Evaluation (Phase 10, Day 43)
## Cloud Log Anomaly Detection for Proactive Fault Management

Days 40–42 found four weaknesses. Day 43 fixed them, and the check run found and fixed a fifth. Check run `live3`
(16 Nov 2026, 14:53–15:13 UTC): silent_service and cascading_failure with random start offsets, 68,265 events, all
services live, Telegram on; a second detection service started on purpose during the warm-up and stopped after
about 20 s. Raw results: `experiments/results/latency/live3.json`, `live3.md`, `feed-live3.jsonl`.

---

## 1. What was changed

| # | Weakness (found on) | Change | Code |
|---|---|---|---|
| 1 | Two detection services split the partitions; each judged the services it could not see as silent and raised false CRITICAL alerts (Day 42) | Detection checks that it holds all partitions of logs.raw; otherwise it warns and does not judge (nothing is committed, nothing lost) | `detection/service.py` |
| 2 | Telegram sends held up the next alerts: +0.9 s per alert, up to 13.6 s on a slow connection (Day 41) | Messages are queued and sent by one background thread, in order; storing and publishing alerts never waits | `alerting/background.py`, `alerting/service.py` |
| 3 | A minute in which all traffic starts or stops looks like a volume drop on every service (Day 42) | Such minutes are not judged, like the first minute after start-up; one silent service is still judged | `detection/edges.py` |
| 4 | All faults of a run started at the same second of the minute, so the delay was measured at one position (Day 40) | Generator option `--jitter S`: each scenario starts 0–S s later (seeded) | `log_generator/scenarios.py`, `generator.py` |
| 5 | Found by the first check run: after partitions changed hands, detection kept the old per-partition event times, closed re-read minutes too early and dropped the replayed events as late (false "no logs" CRITICAL for four services) | The watermark is reset together with the open windows when partitions are revoked or lost | `detection/watermark.py`, `detection/service.py` |

Unit tests: 20 new (edges 8, background sender 6, jitter 5, watermark reset 1).

## 2. Check run results

### Guard against a second detection service (1, 5)

| Moment | Detection service 1 | Detection service 2 |
|---|---|---|
| second service starts | `this process has 1 of 3 partitions … not judged` | `this process has 2 of 3 partitions … not judged` |
| second service stops (Ctrl+C) | `2 open windows discarded and rebuilt from Kafka`, `all partitions assigned again; judging resumes` | `Events 4,584 … windows stored 0 … events in open windows (to be replayed): 4584` |
| afterwards | 14:54 and 14:55 complete for all five services; at the end `late 0` | — |

No minute was judged while the partitions were split, and no event was lost: the second service's 4,584 events
were not committed and were read again by the first. In the first check run (without fix 5) the same switch-back
dropped 6,755 events as late.

### Traffic edges (3)

`14:53 UTC  traffic started during this minute; not judged` (traffic began at 14:53:56) and
`15:13 UTC  traffic stopped during this minute; not judged` (traffic ended at 15:13:29). Before Day 43 these
minutes were scored like any other.

### Telegram in the background (2)

| Several alerts in the same second | Shown on the dashboard after |
|---|---|
| Day 41 (silent_service, 3 alerts) | 1.05 s, 1.89 s, 2.85 s |
| Day 43 (silent_service, 4 alerts, 14:57:06) | 1.05 s, 1.05 s, 1.10 s, 1.10 s |

| Stage | Day 41 (live1) | Day 43 (live3) |
|---|---|---|
| Anomaly → alert opened (median / max) | 0.66 / 1.83 s | 0.79 / 1.05 s |
| Anomaly → new alert on the dashboard (median / max) | 1.33 / 2.85 s | 0.85 / 1.10 s |
| Alert opened → Telegram sent (median / max) | 0.97 / 1.59 s | 1.75 / 13.97 s |

Alerts no longer wait for each other. The Telegram messages themselves now queue behind each other (four at once
take about four send times), and one send was slow (about 14 s; Telegram's own response time, see the night of
14 Nov in latency-results.md). This no longer delays any alert or the dashboard, which is the purpose of the
change; Telegram counts: 24 sent, 0 failed.

### Random start offsets (4) and detection

| Incident | Fault starts | Fault in its first minute | → first anomaly | → first alert | → first Telegram |
|---|---|---|---|---|---|
| silent_service | 14:56:04.8 | 55 s | 60.6 s | 61.5 s | 62.5 s |
| cascading_failure | 15:04:30.4 | 30 s | 35.5 s | 35.7 s | 97.4 s |

- Both offsets differ from the earlier runs (:09, :57, :37) and both fit the delay model of
  live-evaluation-results.md §3: rest of the minute (55.2 s, 29.6 s) + about 5.5–6 s.
- cascading_failure began with a MEDIUM latency alert for order-service; Telegram is sent from HIGH, which came one
  minute later with payment-service (by design, as on Day 41).
- Other stages as on Day 41: log stored 0.56 s median (p95 1.04 s); minute end → anomaly 6.10 s; anomaly →
  dashboard 0.01 s.

## 3. Limits

- One check run; the guard was tested with one extra process, the edges once each.
- At the start of live3 the detection service re-read minutes 13:53–14:07 left over from the failed first check run
  (where order-service's events had already been committed by the faulty version); these minutes showed order-service
  as silent. This was the state left by the bug, not new behaviour, and cannot build up with fix 5.
- The detection delay over many fault positions still needs a full evaluation with `--jitter 60` (5 runs).