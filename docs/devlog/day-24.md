# Day 24 — Live detection service

## Done
- backend/detection/service.py: Kafka consumer (detection-group) -> Drain (model's saved state) -> windows ->
  active model -> severity -> PostgreSQL. Options: --idle-exit, --group.
- backend/detection/store.py: idempotent writes to detection_windows and anomalies (one transaction per batch).
- backend/detection/offsets.py: OffsetTracker (commit only offsets of closed and stored windows).
- backend/detection/watermark.py: per-partition watermark (see below).
- backend/detection/scoring/severity.py: severity bands and the no-logs rule.
- windowing.py: sample event ids per window (errors first), closed_before.
- Removed placeholder backend/detection/predict.py.
- tests: test_severity_offsets.py (5), test_watermark.py (5), test_windowing.py (now 9); unit total 116.
- docs/design/detection-design.md v1.3.

## Results
- First live run (error_burst + silent_service, real time): payment and gateway CRITICAL at 07:56 with 39% / 8.3%
  error rates; no anomalies in the normal minutes before.
- Final replay of all logs in Kafka (both runs, new consumer group): 68,345 events, 0 late, 0 invalid,
  620 windows, 26 anomalies, 0 events left in open windows.

| Fault | Live run (run-20261113-075354) | Fast run (run-20261113-081141) |
|---|---|---|
| Error burst (payment) | payment + gateway at 07:56, 07:57 | payment + gateway at 08:13, 08:14, 08:15 |
| Silent auth | auth no_logs at 08:00; HIGH at 08:01 (partial window) | auth no_logs at 08:18 |
| Gateway during silent auth | flagged from 07:59 (6 s of fault in the window) | flagged from 08:17 |
| Order/payment during silent auth | flagged 08:00–08:01 (6–31 logs) | flagged 08:18 (6–7 logs), order LOW 08:19 |

- No anomaly in any normal minute (50 normal service windows across both runs).
- Order and payment go nearly silent while auth is down: login, order lookups and checkouts need auth, so the
  gateway answers 503 and those requests never reach them. Detected without being modelled explicitly.
- The gap between the runs produced one "no traffic" warning, not anomalies.

## The watermark bug (three attempts)
1. Watermark = latest event time over all partitions. Restarting the service made it catch up on a backlog;
   Kafka delivered partition 0 (inventory) first, the watermark jumped ahead and closed windows before
   partitions 1 and 2 delivered: 13,835 events dropped as late, false "no logs" CRITICAL anomalies.
2. Watermark = minimum over partitions seen so far. Partitions that had delivered nothing yet were ignored:
   23,353 late events.
3. Watermark = minimum latest event time over partitions that still have unread data (position vs Kafka
   high-water mark); no closing while such a partition has delivered nothing; wall clock when all are caught up.
   Result: 0 late events in a 68,345-event replay.
- The bug did not appear in the live run (partitions flowed at the same pace) and only showed after a restart.
  The late-event counter (Day 21) exposed it.

## Problems faced
- Stack had stopped (Docker exited); the service reported PostgreSQL unreachable instead of crashing.
- Wrong results from the broken runs were deleted from detection_windows and anomalies before re-testing.
- Severity saturates: nearly all real faults score ~1.0 (CRITICAL); calibration on Day 25.