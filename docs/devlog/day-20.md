# Day 20 — Error analysis and Phase 5 wrap-up

## Done
- experiments/run_error_analysis.py; results in experiments/results/error_analysis_hdfs_novel_normal.csv and
  error_analysis_bgl_new_templates.csv.
- docs/research/research-plan.md v2.0: verified references, RQ1 and RQ2 answered with results, threats to validity.
- docs/design/detection-design.md: Phase 6 design decisions, each linked to offline evidence.
- Phase 5 (offline ML research) complete.

## HDFS: the 77 novel normal test blocks
- Only 2 distinct count vectors; 0 of 77 identical to any anomalous block -> simple mislabelling rejected.
- Pattern vs typical normal block: 4 instead of 3 "Receiving block"/"addStoredBlock" events; one replication
  sequence (ask to replicate, start transfer, transmitted, received); 0 instead of 3 deletion events.
- Interpretation: blocks re-replicated to a fourth node (normal HDFS recovery) and not yet deleted when the log
  ends (test period = end of trace; normal test blocks have median 13 events vs 19 overall).
- Conclusion: rare but plausible normal behaviour that never occurred in training normals; a limit of
  novelty detection, not label noise (interpretation supported by the evidence above).

## BGL: cause of drift
- 1,134 of 1,538 normal test windows (73.73%) contain templates unseen among training normals; 52 such templates.
- Only 1 of the 52 occurred in training anomalous windows -> drift is real, not an artefact of training on
  normal windows only.
- The 5 most frequent explain 72.0% of affected windows. Most first appear on 2005-11-15 (test starts 2005-11-12):
  periodic summaries of automatically corrected hardware errors (DDR, torus, L3, tree receiver).
- Interpretation: a monitoring/firmware change on 15 Nov switched on new routine reports (several summary messages
  starting on the same day). Drift is a step change, not gradual.
- Explains Day 19: retraining used data up to 12 Nov, before the change, so it could not help.

## Consequences
- Novelty detectors flag both real anomalies and rare/new normal behaviour; precision depends on how stable the
  system is.
- After a step change, the system should adapt: retrain on post-change normal data, or let an operator mark a new
  message type as normal (design idea for the live system; future work).

## Problems faced
- None.