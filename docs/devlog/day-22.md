# Day 22 — Choosing the live detector configuration

## Done
- backend/detection/pipeline.py: events -> Drain -> windows (shared by training, evaluation and the live service);
  drops the partial first/last windows of a data set.
- backend/detection/live_model.py: LiveDetector (global or per-service, PCA or One-Class SVM, raw or log counts,
  label-free 99.9th-percentile threshold, normalised score).
- tests/unit/test_live_model.py: 10 tests.
- experiments/compare_live_configs.py; results in experiments/results/live_config_comparison.csv.
- Training data: 3 x 2 h of normal traffic (seeds 1, 2, 3; ~443k events each), 1,785 windows, 31 templates.
- docs/design/detection-design.md v1.2.

## Evaluation setup
- all_faults run (seed 42, run-20261110-153448): 200 windows, 21 faulty (7 full, 14 edge), 20 quiet, 7 fault records.

## Results

| Config | Precision | Recall | F1 | Full recall | Edge recall | Incidents | Quiet false alarms |
|---|---|---|---|---|---|---|---|
| A global PCA raw | 0.571 | 0.762 | 0.653 | 0.857 | 0.714 | 6/7 | 0 |
| B global PCA log | 0.571 | 0.952 | 0.714 | 1.000 | 0.929 | 7/7 | 0 |
| C per-service PCA raw | 0.567 | 0.810 | 0.667 | 0.857 | 0.786 | 7/7 | 0 |
| D per-service PCA log | 0.543 | 0.905 | 0.679 | 1.000 | 0.857 | 7/7 | 0 |
| E per-service OCSVM raw | 0.345 | 0.952 | 0.506 | 1.000 | 0.929 | 7/7 | 3 (15%) |
| F per-service OCSVM log | 0.357 | 0.952 | 0.519 | 1.000 | 0.929 | 7/7 | 3 (15%) |

- Config B, first flag after fault start: error_burst 11 s, latency_spike 11 s, new_error 11 s,
  silent_service 71 s (2/3 windows), cascading order 11 s / payment 11 s / inventory 41 s.

## Decision
- Global PCA with log counts (B): best on every measure; simpler than per-service models.

## Findings
- Log counts help on our services (very different volumes), consistent with BGL in RQ2.
- With raw counts, PCA missed the silent service (A: 0/3): an empty window lies along the volume direction of
  the normal subspace. Log scaling helps (B: 2/3); the zero-logs rule override covers the rest.
- One-Class SVM detects as much but raised false alarms in 15% of quiet windows.
- Low precision (~0.57) comes from dependent services reacting during incidents, not from quiet-period alarms.

## Problems faced
- Normalised scores above 1 for One-Class SVM: raw / (raw + threshold) assumes non-negative scores. Replaced by
  an exponential normalisation around the threshold, valid for any score scale (flags unchanged).
  - With near-identical synthetic test windows, PCA scores were floating-point noise (~1e-28); a window just above
  the threshold got a normalised score of exactly 0.5 and contradicted its flag. Fixed by deciding the flag on the
  raw score and clamping the normalised score to the matching side of 0.5.

## Open points
- Only 20 quiet windows: measure the false alarm rate on a separate fault-free run (Day 23).
