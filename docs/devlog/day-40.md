# Day 40 — Live evaluation results; consumers survive a lost group membership

## Evaluation run (night of 14–15 Nov)
- Completed: r1, r2, r3 (n = 3 of the planned 5) and the fault-free hour n1. Results committed
  (experiments/results/live/, commit "eval: live evaluation results").
- Two attempts were discarded: the laptop slept (lid closed: 25 min pause; later screen-off on a Modern Standby
  laptop: 22 min pause). The runner stopped on the generator's delivery failure instead of scoring a broken run.
  Settings used for unattended runs: `powercfg /change standby-timeout-ac 0`, `monitor-timeout-ac 0`,
  `hibernate-timeout-ac 0`, lid action "do nothing" on AC; restored afterwards.
- Night totals: 819,535 events (0 invalid, 0 late), 145 anomalies, 52 alerts (all auto-resolved), 112 Telegram
  messages (0 failed).

## Results (docs/testing/live-evaluation-results.md)
- 15/15 incidents detected; 100 % recall on minutes fully inside a fault; 100 % precision counting reactions near
  incidents (strict 54.5 %); 0/30 false alarms in quiet minutes; fault-free hour 1/285 (0.35 %), LOW, 0 alerts;
  2.5 alerts per incident.
- Detection delay 8–69 s, mean 52 s, fully explained: rest of the minute + ≈ 5 s (grace period + under a second of
  processing), plus one minute when the first partial minute holds too little of a gradual fault. The protocol
  sampled only two positions in the minute (:09, :57) because scenarios are spaced in whole minutes; next time each
  scenario needs a random start offset.
- Prediction "30–35 s" refined rather than confirmed; false-alarm and detection predictions confirmed.

## Fix: consumers crashed after a long pause
- Symptom: after the laptop slept, ingestion stopped with
  `KafkaException _ASSIGNMENT_LOST: Commit failed: Local: Group partition assignment lost`. Detection and
  alerting commit the same way and could have crashed as well.
- Cause: after more than the session timeout without heartbeats the group coordinator removes the consumer; its
  next synchronous commit fails. The consumer would rejoin by itself on the next poll.
- backend/common/kafka_commit.py: `commit_safely()` reports the recoverable errors (assignment lost, illegal
  generation, unknown member, rebalance in progress, nothing to commit) as a warning and returns False; other
  errors are still raised.
- Ingestion and alerting use it; replay is harmless there (event_id as document id; anomalies already linked to an
  alert are skipped).
- Detection additionally rebuilds its state: on revoked or lost partitions (`on_revoke`, `on_lost`) it discards its
  open windows and pending offsets (`WindowAggregator.discard_open`, `OffsetTracker.clear`), so replayed events are
  not counted twice; closed windows stay closed (replayed events for them are dropped as late; the store ignores
  duplicate windows). Ignored during shutdown, where open windows are replayed after a restart anyway.
- tests/unit/test_kafka_recovery.py: 9 tests (normal commit, five recoverable codes, other errors raised, open
  windows discarded while closed ones stay closed, tracker cleared).

## Next
- Day 41: speed (log creation → stored; fault → anomaly → alert → Telegram).