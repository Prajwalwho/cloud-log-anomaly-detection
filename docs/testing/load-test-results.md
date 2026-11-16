# Load Test (Phase 10, Day 42)
## Cloud Log Anomaly Detection for Proactive Fault Management

Does the pipeline keep up when traffic rises? Four steps of 5 minutes, back to back: 20, 50, 100 and 200 requests per
second (1×, 2.5×, 5× and 10× the normal rate; about 3 log events per request). Everything ran on one laptop (Windows,
Docker Desktop for Kafka, PostgreSQL and Elasticsearch; Python services on the host).
Tool: `scripts/load_test.py` (rules in `backend/detection/evaluation/load.py`). Raw results:
`experiments/results/load/l1.*`, `l2.*` and the generator logs next to them.

A step **keeps up** when the generator sends on time and Kafka confirms every event, ingestion stores logs with a
p95 under 5 s and its Kafka lag does not keep growing, and detection judges each minute with a p95 under 10 s after
it ends. Each step is measured from its second minute.

---

## 1. Runs

| Run | What happened | Used for |
|---|---|---|
| l1 | The ingestion service had stopped at start-up (Elasticsearch was still starting), so no log was stored; one detection service ran normally | detection (§3) |
| l2 | All services running, but two detection services and two alerting services were running at the same time (left over from l1) | ingestion (§2) |

The l2 duplicate was found afterwards with `Get-CimInstance Win32_Process` (on Windows each service shows as two
`python.exe` processes, the venv launcher and the interpreter; there were two such pairs for detection and for
alerting). Both runs used the same seeds, so the traffic was identical.

## 2. Ingestion (l2): keeps up at 10× the normal rate

| Requests/s | Events/s | Log → stored p50 | p95 | max | Max ingestion lag | Keeps up |
|---|---|---|---|---|---|---|
| 20 | 74.5 | 0.57 s | 1.05 s | 1.14 s | 129 events | yes |
| 50 | 182.2 | 0.58 s | 1.05 s | 1.18 s | 238 events | yes |
| 100 | 365.4 | 0.56 s | 1.04 s | 1.19 s | 503 events | yes |
| 200 | 734.9 | 0.39 s | 0.71 s | 1.22 s | 582 events | yes |

- 407,128 events in 20 minutes, all confirmed by Kafka; ingestion had nothing left to store when the last step ended.
- Latency does not grow with load; at 200 requests/s it is even lower. The ingestion service reads up to 500 events
  per batch and otherwise waits up to 1 s for a batch to fill: at low rates most events wait for that timeout, at
  high rates the batch fills sooner.
- The lag never exceeded 600 events (under one second of traffic).

## 3. Detection (l1): judges every minute on time at every load

| Requests/s | Events/s | Minute end → judged p50 | p95 | Flagged windows |
|---|---|---|---|---|
| 20 | 74.5 | 5.71 s | 6.03 s | 0 of 20 |
| 50 | 182.2 | 5.71 s | 5.92 s | 1 of 20 |
| 100 | 365.4 | 5.87 s | 6.18 s | 16 of 20 (LOW) |
| 200 | 734.9 | 5.78 s | 5.97 s | 20 of 20 (LOW) |

- The time after a minute closes stays at the 5-s grace period plus under a second at every rate: parsing (Drain),
  windowing and scoring 44,000 events per minute are not a bottleneck.
- **Flagged windows**: the model was trained at 20 requests/s, so traffic at 5× and 10× is unusual for it. It flagged
  those minutes as LOW ("unusual log pattern"), which opens no alert. In a real deployment a lasting change of the
  normal load needs a retrained model (or features that do not depend on absolute volume).
- payment-service showed "1 new message type" (MEDIUM) twice at 200 requests/s: a rare message that the training data
  never contained appeared once traffic was ten times higher. One MEDIUM alert was opened; correct behaviour.

## 4. Resources (snapshot in the middle of each step, l2)

| Requests/s | Elasticsearch | Kafka | PostgreSQL |
|---|---|---|---|
| 20 | 2.6 % CPU, 1.62 GiB | 14 % CPU, 1.00 GiB | 0.0 %, 44 MiB |
| 50 | 2.0 %, 1.63 GiB | 14 %, 1.01 GiB | 0.0 %, 44 MiB |
| 100 | 62 %, 1.63 GiB | 13 %, 1.04 GiB | 0.1 %, 44 MiB |
| 200 | 3.5 %, 1.61 GiB | 141 %, 1.12 GiB | 0.0 %, 44 MiB |

Single `docker stats` readings: CPU jumps (Elasticsearch merging segments, Kafka flushing) depend on the moment and
are not a trend. Memory is flat: about 2.8 GiB for the stack at every load. PostgreSQL only stores 5 windows per
minute, whatever the traffic.

## 5. Finding: detection must run as one process

With two detection services in the same consumer group, Kafka gave each of them some of the three logs.raw
partitions. Logs are keyed by service, so each process saw only some services and judged the others as silent:
order-service showed "0 logs, CRITICAL" every minute and all five services got "stopped logging" alerts (13–19
occurrences each) although every service was logging. This is a design limit, not a test error: each detection
process assumes it sees every service. Day 43 adds a guard: when detection is not assigned all partitions, it warns
and stops judging instead of raising false alerts. (Ingestion and alerting can run as several processes; their work
divides correctly.)

## 6. Summary for the report

- On one laptop the pipeline handled **735 events per second (44,000 per minute), 10× the normal load**, with logs
  stored in **0.7 s (p95)** and every minute judged **≤ 6.2 s** after it ended; Kafka confirmed all 407,128 events.
- No stage was close to its limit, so the maximum throughput was not reached; the next step would be 400 requests/s.
- Limits: one run per service (ingestion l2, detection l1), 5-minute steps, a single machine shared by generator,
  services and containers; CPU readings are snapshots.