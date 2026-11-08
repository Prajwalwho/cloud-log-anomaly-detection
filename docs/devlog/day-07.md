# Day 7 — Fault injection and ground truth

## Done
- backend/log_generator/scenarios.py: Fault and Scenario definitions; 5 scenarios
  (error_burst, latency_spike, new_error, silent_service, cascading_failure); schedule builder.
- generator.py: fault injection (error rate, latency multiplier, new error template, silent service),
  scenario CLI options (--scenario, --warmup, --gap, --list-scenarios, --ground-truth),
  ground-truth file written per run (contracts.md, Section 5.4).
- scripts/summarize_logs.py: per-minute overview and per-service detail, with fault windows marked.
- tests/unit/test_scenarios.py: 11 tests (validation, each fault type, schedule, ground-truth format).
  Total unit tests: 20, all passing.
- .gitignore: data/ground_truth/ ignored (generated per run).

## Design decisions
- Each scenario targets a different detection ability: error rate, latency, new log templates,
  missing logs, and multi-service incidents.
- Timeline: 5 min normal warmup, then each scenario followed by 5 min of normal traffic,
  so false positives can be measured in the gaps.
- Ground truth is written before generation and never included in the log events (no label leakage).
- With no faults, output is identical to the Day 6 generator for the same seed (verified by test).
- Faults cannot target the api-gateway; the gateway shows downstream faults as 502/503 errors.

## Results — full run (all scenarios, seed 42, 2,460 s, 148,483 events)

| Scenario | Service | Normal | During fault (full minute) |
|---|---|---|---|
| error_burst | payment | ~0% errors | 33.8% errors |
| latency_spike | order | median 24 ms, ~1.5% WARN | median 150 ms, 92.3% WARN |
| new_error | inventory | ~0.1% errors | 11.7% errors (new template) |
| silent_service | auth | ~900 logs/min | 0 logs/min; gateway 55.8% errors |
| cascading_failure | order → payment → inventory | baseline | staged: order slow, then payment 28%, inventory 14% errors |

Overall: ERROR 1.77% and WARN 2.05% (vs 0.22% and 0.87% in normal-only traffic).

## Observations for detection and evaluation
1. Faults start mid-minute, so the first and last window of each fault is only partly faulty
   (e.g. 8.6% instead of ~34% errors). These edge windows are the hardest to detect.
   Evaluation will label a window faulty if it overlaps a fault and report edge windows separately.
2. silent_service also silences order-service and payment-service (their requests pass through auth),
   but the ground truth labels only auth-service. Flagging order/payment then is correct behaviour.
   Evaluation will therefore be done at two levels: service level (root cause) and incident level
   (any alert during the incident).
3. Normal traffic volume varies between ~850 and ~1,600 gateway logs/minute (sinusoidal load), so
   raw counts alone cannot indicate anomalies; features need rates (error %, warn %) and latency.

## Notes for the detection service (Phase 6)
- silent_service produces windows with zero logs. The detector must create a window for every known
  service even when no logs arrive, otherwise this fault is invisible.
- latency_spike produces almost no ERROR logs; features must include latency, not only error counts.
- new_error introduces a template never seen in training; a "new_templates" feature is needed.
- The first and last minute of a run are partial windows (low counts) and should be excluded or handled.

## Problems faced
- Passed the placeholder `<run-id>` literally to summarize_logs.py; replaced it with the real run ID.