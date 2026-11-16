# Day 43 — Improvements from the evaluation (Phase 10 complete)

## Built
- Detection partition guard: a detection process that does not hold all partitions of logs.raw warns and does not
  judge (another process in the same group would make services look silent). Nothing is committed meanwhile.
- `backend/alerting/background.py`: Telegram messages sent by one background thread, in order; an alert with a
  queued message counts as notified; a second Ctrl+C no longer prints a traceback.
- `backend/detection/edges.py`: minutes in which all traffic started or stopped are not judged.
- Generator `--jitter S`: random 0–S s start offset per scenario (seeded); gaps kept.
- Fix found by the check run: `PartitionWatermark.clear()` on revoked or lost partitions. Without it the old event
  times closed re-read minutes early and the replayed events were dropped as late.
- 20 new unit tests.

## Check runs
- First attempt: laptop on battery, screen-off suspended everything for 42 minutes (`-ac` power settings only apply
  on the charger). Unusable, but it showed the Day 40 recovery working (ingestion rejoined and caught up at
  ~4,500 events/s; detection rebuilt its windows).
- live2: guard, traffic-started and background Telegram worked, but the switch-back after the second detection
  service dropped 6,755 events as late → stale watermark → fixed (commit "reset watermark").
- live3 (docs/testing/improvements-results.md): guard both ways, `late 0`, both edges skipped, four simultaneous
  alerts on the dashboard within 1.05–1.10 s (Day 41: 1.0 / 1.9 / 2.9 s), jittered faults at :04.8 and :30.4
  detected after 60.6 s and 35.5 s (rest of the minute + ~6 s), Telegram 24 sent / 0 failed.

## Lessons
- Check the charger: `(Get-CimInstance Win32_Battery).BatteryStatus` must be 2.
- Any state built from Kafka positions (open windows, offsets, watermark, minute bounds) has to be reset together
  when partitions change hands.

## Phase 10 summary (Days 39–43)
- Live evaluation: 15/15 incidents, 0 false alarms in quiet minutes, 1 LOW in a fault-free hour.
- Speed: log stored 0.6 s; anomaly ≈ 6 s after the minute; dashboard +0.01–0.06 s; Telegram +1 s.
- Load: 735 events/s (10× normal) without falling behind.
- Robustness: survives sleep / lost group membership, duplicate detection processes, traffic edges.

## Next
- Phase 11: documentation (in-app Docs section, repository docs, study guide).