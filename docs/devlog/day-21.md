# Day 21 — Windowing engine and live features (Phase 6 starts)

## Done
- backend/detection/windowing.py: WindowAggregator (60-s tumbling windows per service, empty windows for every
  known service, watermark-based closing, late events counted and dropped).
- backend/detection/features/extractor.py: WindowFeatureExtractor (template counts + unseen, log_count,
  error_rate, warn_rate, latency mean/p95, new_templates; optional log scaling; summary for the database).
- backend/detection/preprocessing/parser.py: SERVICE_LOG_MASKS = default masks + alphanumeric identifier mask.
- tests: test_windowing.py (7), test_extractor.py (6), test_parser.py (now 10).
- experiments/replay_windows.py: replays a generated log file through windowing and features, compared with
  ground truth.
- docs/design/detection-design.md v1.1.

## Replay results (all_faults.jsonl, run-20261110-153448)
- 148,483 events, 210 windows (42 min x 5 services), 0 late events, 1 empty window (silent auth-service, 16:01).
- After the identifier mask: 31 templates, 28 in the 5-minute warmup vocabulary.

| Fault | Signal in the windows |
|---|---|
| error_burst (payment) | error rate 0% -> 32.8% |
| latency_spike (order) | p95 ~60 ms -> 340 ms, warn rate -> 92%, error rate unchanged |
| new_error (inventory) | new_templates = 1 (only non-zero value in the run), error rate ~11% |
| silent_service (auth) | 0 logs in the full fault window |
| cascading_failure | order slow from 16:07, payment errors from 16:08, inventory errors from 16:09 |

- Edge windows (fault starting/ending mid-minute) show weaker signals than full fault windows.

## Problems faced
- Wrong ground-truth file used after regenerating the log file; a log file and its ground truth belong together.
- Template explosion (36,758 templates; hundreds of "new templates" in normal windows): user ids (u6601) and
  transaction ids (txn_c9731bc4b8) mix letters and digits and were not masked. Fixed with an alphanumeric
  identifier mask in a separate mask set, so the offline HDFS/BGL results stay reproducible.
- Lesson: the Day 13 parser test covered only the payment failure message (no transaction id) and missed this;
  tests must cover the realistic messages of each service.
- 5 minutes of warmup missed rare normal templates (3 of 31): training needs hours of normal traffic.