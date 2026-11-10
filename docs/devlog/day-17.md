# Day 17 — BGL dataset: parsing and exploration

## Done
- Downloaded BGL from LogHub (Zenodo record 8196385) into data/raw/BGL (not committed).
- experiments/parse_bgl.py: per-line parsing (label, timestamp, level, content), Drain with BGL-specific masks,
  output data/processed/bgl_events.npz, bgl_templates.csv, bgl_parse_info.json (not committed).
- experiments/notebooks/06_bgl_exploration.ipynb.

## Parser tuning (first 200,000 lines)
- First run at threshold 0.9: 275 templates; the rarest were CPU register dumps ("<NUM>:9a94a344 ...") split into
  one template each, because bare hexadecimal values (no "0x") were not masked.
- Added BGL-only masks: NODE (node names such as R02-M1-N0-C:J12-U11) and bare HEX (6+ hex characters with at
  least one digit). Kept out of the shared default, where it would change HDFS and generator templates.

| Threshold (with new masks) | Templates | Register-dump template |
|---|---|---|
| 0.5 | 118 | `<NUM>:<HEX> <NUM>:<HEX> <*> <*>` (different formats merged) |
| 0.7 | 140 | still contains `<*>` |
| 0.9 | 151 | fully masked, no wildcard |

- Chosen: 0.9 (same as HDFS). The 40 rarest templates at 0.9 were all genuinely different messages.

## Results (full run)
- 4,747,963 lines in 110 s, 0 malformed; 2005-06-03 → 2006-01-04 (215 days); timestamps in order.
- 348,460 alert lines (7.34%), 41 alert categories; KERNDTLB 152,734, KERNSTOR 63,491, APPSEV 49,651.
- 2,845 templates (728 never alert, 2,113 always alert, 4 mixed).

| Level | Alert | Normal | Alert % |
|---|---|---|---|
| FATAL | 348,398 | 506,797 | 40.74 |
| FAILURE | 62 | 1,652 | 3.62 |
| INFO | 0 | 3,735,813 | 0 |
| ERROR | 0 | 112,355 | 0 |
| WARNING | 0 | 23,357 | 0 |
| SEVERE | 0 | 19,213 | 0 |

- Rule "level ERROR/SEVERE/FATAL/FAILURE" (line level): precision 0.353, recall 1.000.
- Alerts on 189 of 215 days; the 5 busiest days contain 66.7% of all alerts.

| Window | Non-empty windows | Anomalous % | Median lines |
|---|---|---|---|
| 1 min | 27,659 | 6.54 | 4 |
| 5 min | 14,501 | 7.25 | 6 |
| 15 min | 8,590 | 9.99 | 12 |
| 30 min | 5,773 | 13.13 | 20 |
| 1 h | 3,607 | 18.44 | 49 |
| 6 h | 826 | 49.52 | 752 |

## Decisions
- Drain threshold 0.9 with BGL masks NODE and bare HEX.
- Window size 15 minutes (balance between counts per window and a meaningful anomaly share);
  5 min and 1 h as optional sensitivity checks.

## Findings
- In BGL the message type almost determines the label (only 4 of 2,845 templates are mixed). Expected consequence:
  a "template unseen in training normals" rule will be very strong; its weakness will be normal templates that
  first appear later in time.
- Log level is necessary but not sufficient (all alerts are FATAL/FAILURE, most FATAL lines are normal).
- Alerts are bursty; the chronological split will strongly affect results and must be reported.
- Both benchmarks appear largely solvable by recognising message types, which motivates the live evaluation
  with faults that create no new templates (e.g. latency_spike).

## Open points
- 2,845 templates vs 151 in the first 200k lines: check the rare normal templates for remaining over-splitting
  before building features (Day 18).
- ~316 lines with a shifted level column.

## Problems faced
- Register dumps over-split into one template each; fixed with a bare-hex mask.