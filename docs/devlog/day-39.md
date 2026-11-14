# Day 39 — Live evaluation plan and tooling (Phase 10, RQ3)

## Done
- docs/testing/live-evaluation-plan.md: why repeated runs (variance was a stated threat to validity), the runs
  (5 fault runs, seeds 101–105, scenario order rotated so every scenario takes every position; 1 fault-free hour,
  seed 201), definitions (faulty, full, incident, near an incident, quiet, idle, detection and alert delay), the
  metrics, the expected values written down before running, the procedure and threats to validity.
- backend/detection/evaluation/live_run.py: the metrics as pure functions on plain records (fault, window, alert):
  per fault record, per incident (detected, delay, first service, worst severity, anomalies, alerts, alert delay,
  Telegram, time to auto-resolve), window level (precision, recall, F1, full-window recall, precision counting
  reactions near incidents, quiet false alarms with reasons), alerts outside incidents, fault-free runs, and the
  summary over runs (mean, standard deviation, min, max; per scenario).
- scripts/live_eval.py: `run <ground truth>`, `normal --from/--to` or `--minutes`, `summary`; loads windows,
  anomalies and alerts of the active model from PostgreSQL, prints a table and saves
  experiments/results/live/<label>.json; the summary writes summary.json and summary.md (table for the paper).
- scripts/run_live_evaluation.ps1: runs r1–r5 and n1 back to back, waits 7 minutes, evaluates and summarises;
  `-Runs`, `-SkipNormal`, `-OnlyNormal` for partial runs.
- tests/unit/test_live_run_metrics.py: 5 tests on a hand-made run (incident grouping, window-level metrics with an
  expected gateway reaction and a quiet false alarm, incident and alert metrics, fault-free run, summary).

## Decisions
- Evaluated period: 4 minutes before the first fault to 4 minutes after the last. The first test with 10 minutes
  showed the problem: it reaches into the previous run, where the hand-over between two generator processes leaves
  a partial minute that the volume rule flags. 4 minutes stays inside the run's own 5-minute warm-up and final gap.
- Alerts belong to an incident if they open from 2 min before to 4 min after it; later ones count as outside.
- Two precisions are reported: strict (only the faulty service's minutes are true) and counting reactions near
  incidents (the gateway reporting a downstream failure is correct behaviour, not a detector error).
- The fault-free hour leaves out its first 2 minutes and last minute (traffic starting and stopping).
- The metric code has no database or numpy dependency, so it is tested in isolation.

## Next
- Run the evaluation (about 4 h 40 min unattended), commit the results, then RQ4: pipeline latency and throughput.