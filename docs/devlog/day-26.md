# Day 26 — End-to-end real-time run (Phase 6 complete)

## Done
- pipeline.py: too_far_in_future() — contract rule (more than 5 min in the future is invalid).
- service.py: future-timestamp guard (counted as "future", skipped before it can move the watermark);
  --allow-future for fast-mode test replays.
- severity.py: ratios shown with two decimals (2.97x instead of a misleading 3.0x).
- scripts/send_future_log.py: robustness test (one well-formed event dated 2030).
- scripts/check_detection.py: compares stored windows/anomalies with a ground-truth file (per fault record,
  per incident, quiet-window false alarms, service-level precision/recall, real time-to-detect).
- tests: test_future_guard.py (3); unit total 126.
- docs/design/detection-design.md v1.5.

## End-to-end run (real time, run-20261113-115333)
- Generator, ingestion and detection running together; all five scenarios, 2-minute gaps.
- The generator stopped after 1,108 s of the scheduled 1,380 s (most likely an accidental Ctrl+C): the cascading
  failure ran only 28 s of its 180 s; everything before was complete.

| | Ingestion -> Elasticsearch | Detection -> PostgreSQL / Kafka |
|---|---|---|
| Received | 66,278 | 66,278 |
| 2030 event | rejected (timestamp), dead-lettered | skipped (future) |
| Processed | 66,277 stored (logs-2026.11.13) | 66,277 analysed, late 0, invalid 0 |
| Output | 1,028 batches committed | 90 windows, 23 anomalies, 23 published, 0 failed |

- Both consumers, with separate validation, processed exactly the same events.

| Incident | Detected after | First signal | Fault-service windows flagged |
|---|---|---|---|
| error_burst | 32 s | gateway MEDIUM | payment 3/3 (HIGH, CRITICAL, CRITICAL) |
| latency_spike | 32 s | order HIGH | order 3/3 (HIGH x3) |
| new_error | 33 s | gateway MEDIUM | inventory 3/3 (HIGH x3, 1 new message type) |
| silent_service | 32 s | gateway CRITICAL | auth 1/3 (CRITICAL, no logs) |
| cascading_failure | 33 s | order MEDIUM | order 1/1 (run stopped) |

- 5/5 incidents detected; time-to-detect matches the design: fault at :33.6 -> window end 26.4 s later
  + 5 s grace + ~1 s processing ≈ 32 s.
- Service level: precision 0.478, recall 0.846 (TP 11, FP 12, FN 2); false positives are dependent services
  reacting during incidents.

## Findings
- Silent auth: the 12:09 window had 34% of normal volume but was not flagged by the model; severity rules
  only grade flagged windows. Candidate for Phase 10: a volume rule that can also flag (test on fault-free
  runs first).
- With 2-minute gaps no window is "quiet" (all within 2 minutes of a fault): false-alarm rates need the
  default 5-minute gaps (the fault-free run gave 0.34%, graded LOW, on Day 25).
- During the latency spike the gateway's own p95 latency rose (1.77x normal, MEDIUM): it waits for order.

## Problems faced
- check_detection.py was first run with the placeholder "<run-id-from-8d>" in the path, then before the run had
  finished (silent and cascading faults showed 0/0 windows = not happened yet).
- Generator stopped early (see above).