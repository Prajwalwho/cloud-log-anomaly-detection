# Pipeline Speed (Phase 10, Day 41)
## Cloud Log Anomaly Detection for Proactive Fault Management

How long each step takes, from a log line being written to the operator's phone and the dashboard.
Run `live1` (16 Nov 2026, 07:13–07:42 UTC): three faults (error_burst, new_error, silent_service, 8 minutes apart),
98,179 events with the generator's default settings (about 60 events per second on average), all services running live
on one laptop.
Measured with `scripts/latency_report.py` (definitions: `backend/detection/evaluation/latency.py`).
Raw results: `experiments/results/latency/live1.json`, `live1.md`, `feed-live1.jsonl`; the stored data of the
evaluation night (14 Nov) in `night.json`, `night.md` (§6).

---

## 1. Stages

| Stage | n | Median | p95 | Max | What it consists of |
|---|---|---|---|---|---|
| Log created → stored in Elasticsearch | 92,140 | **0.61 s** | 1.09 s | 1.60 s | Kafka, ingestion batch (up to 500 events or 1 s), bulk write |
| … → searchable on the Logs page | | + ≤ 5 s | | | Elasticsearch refresh interval (5 s) |
| Minute ends → anomaly stored | 18 | **5.87 s** | 6.37 s | 6.40 s | 5 s grace period + next loop pass (polls up to 1 s) + scoring and storing |
| Anomaly → shown on the dashboard | 18 | **0.06 s** | 0.07 s | 0.09 s | Kafka → API listener → WebSocket |
| Anomaly → alert opened | 8 | **0.66 s** | 1.54 s | 1.83 s | Kafka → alerting service → PostgreSQL (see §3) |
| Anomaly → new alert shown on the dashboard | 8 | 1.33 s | 2.70 s | 2.85 s | the above + publishing to alerts.events + WebSocket |
| Alert opened → Telegram message sent | 5 | **0.97 s** | 1.48 s | 1.59 s | HTTPS round trip to the Telegram Bot API |

The database clock (PostgreSQL in Docker) and the laptop clock differed by less than 0.01 s, so no correction was
needed. The Telegram stage counts alerts that were HIGH or CRITICAL when opened; three alerts opened as MEDIUM and
were notified when they reached HIGH a minute later (§2).

## 2. Fault → anomaly → alert → Telegram

| Incident | Fault starts | → first anomaly | → first alert | → first Telegram |
|---|---|---|---|---|
| error_burst | 07:17:37 | 28.5 s | 29.2 s | 30.9 s |
| new_error | 07:25:37 | 28.5 s | 29.1 s | ≈ 90 s (alerts opened MEDIUM, notified on reaching HIGH one minute later) |
| silent_service | 07:33:37 | 27.8 s | 28.3 s | 29.3 s |

All three faults started at second :37, so 23 s of fault lay in the first minute. The measured times match the model
from the live evaluation (live-evaluation-results.md §3):

> fault → first Telegram ≈ **rest of the minute** (23 s) + **5.9 s** (grace + detection) + **0.7 s** (alert) +
> **1.0 s** (Telegram) ≈ 30.6 s (measured 30.9 s and 29.3 s).

**Everything after the minute closes takes about 7–8 seconds, of which 5 s is the deliberate grace period.** The
rest of the delay is waiting for the minute to end (0–60 s, depending on when the fault starts), plus one more minute
when a fault is too weak to be flagged in its first, partial minute, or when the alert opens as MEDIUM (Telegram is
sent from HIGH upwards).

## 3. Finding: Telegram sends hold up the next alerts

The alerting service handles anomalies one after another, and it sends the Telegram message for an alert before it
handles the next anomaly. When several services fail in the same minute, the later alerts wait for the earlier
messages:

| silent_service, 07:35:05 | Alert shown on the dashboard after |
|---|---|
| auth-service | 1.05 s |
| order-service | 1.89 s |
| payment-service | 2.85 s |

Each step adds about 0.9 s, which is the Telegram send time. With one failing service this costs nothing; with a
cascading failure across four services the last alert is about 3 s late. On a slow connection it is much worse:
during the evaluation night single Telegram sends took up to 10.9 s and alerts opened up to 13.6 s after their
anomaly (§6). Remedy (Day 43): send Telegram messages from a background thread so storing and publishing alerts never
waits for the network.

## 4. Summary for the report

- Log line stored: **0.6 s** median (p95 1.1 s); searchable within about 6 s.
- After a one-minute window closes: anomaly in **5.9 s**, on the dashboard **0.06 s** later, alert **0.7 s** later,
  Telegram **1.0 s** later.
- Fault start → Telegram: **29–31 s** in this run (faults at :37); in general rest of the minute + ≈ 7.5 s.
- The processing time of the system itself (about 2.5 s beyond the 5-s grace period) is small compared with the
  window length; detection speed is governed by the 60-s window (see Day 43 for shorter or overlapping windows).

## 5. Limits

- One run, three incidents, all starting at the same second of the minute; the stage medians rest on 5–92,140
  samples (the small ones are indicative).
- Default load (about 60 events/s). How the stages change at higher rates is the subject of the load test (Day 42).
- Telegram time depends on the internet connection; Elasticsearch percentiles are approximate (t-digest).

## 6. Evaluation night, 14 Nov (stored data, 15 incidents)

`latency_report.py report --label night` over the three fault runs and the fault-free hour of the live evaluation:

| Stage | n | Median | p95 | Max |
|---|---|---|---|---|
| Minute ends → anomaly stored | 102 | 5.92 s | 6.28 s | 6.54 s |
| Anomaly → alert opened | 38 | 1.06 s | 12.43 s | 13.62 s |
| Alert opened → Telegram message sent | 26 | 0.89 s | 8.48 s | 10.93 s |

- Detection after the minute closes is as steady as in live1 (5.9 s, p95 6.3 s).
- The long tails of the alert and Telegram stages come from slow Telegram sends that night; because sends are made
  in line, they also delayed the next alerts (§3).
- Per incident, fault → first anomaly was 55.5–56.8 s (faults at :09), 7.9–9.1 s or 68.0–68.6 s (faults at :57),
  exactly as in live-evaluation-results.md §3. Fault → first Telegram was 57–58 s where the first alert was HIGH or
  CRITICAL, and about one minute more (69–130 s) where it opened as MEDIUM.
- The Elasticsearch stage returned no logs for that night, and the live feed was not recorded, so these two rows
  come from live1 only. Ten alerts of that night have `notified_at` more than 30 s after opening (opened as MEDIUM
  and notified on reaching HIGH, or stored before Day 41, when an escalation still overwrote `notified_at`); they
  are left out of the Telegram stage.