# Day 16 — Isolation Forest, One-Class SVM and the HDFS model comparison

## Done
- backend/detection/models/isolation_forest.py: IsolationForestDetector (200 trees).
- backend/detection/models/one_class_svm.py: OneClassSVMDetector (RBF kernel, standardised features,
  optional training on distinct rows weighted by frequency).
- backend/detection/evaluation/evaluate.py: one shared evaluation for all models (label-free p99.9 and
  validation-tuned thresholds; precision, recall, F1, FP, FN, PR-AUC, ROC-AUC; novel-normal check).
- tests/unit/test_models_ml.py: 6 tests.
- experiments/notebooks/05_hdfs_model_comparison.ipynb: all models + B4 evaluated identically.
- experiments/results/hdfs_model_comparison.csv, hdfs_model_comparison_summary.csv, hdfs_pr_curves.png.

## HDFS results (test set)

| Model | F1 label-free p99.9 | F1 validation-tuned | PR-AUC |
|---|---|---|---|
| B4 lookup table | 0.978 | 0.978 | 0.956 |
| One-Class SVM (nu = 0.001) | 0.971 | 0.976 | 0.999 |
| PCA | 0.965 | 0.960 | 0.995 |
| z-score | 0.002 | 0.774 | 0.756 |
| Isolation Forest | 0.000 | 0.045 | 0.018 |

- One-Class SVM nu chosen on validation PR-AUC: 0.001 (0.9966), 0.005 (0.9956), 0.01 (0.9812),
  0.05 (0.9380), 0.1 (0.9309).
- Fit / score time on 575k blocks: z-score 0.07 / 0.11 s, PCA 0.33 / 0.20 s, IF 0.68 / 4.50 s, OCSVM 1.86 / 3.62 s.

## One-Class SVM training cost (measured)

| Training blocks | Fit (full) | Support vectors (full) | Fit (distinct, weighted) | Rows | Support vectors |
|---|---|---|---|---|---|
| 16,000 | 0.14 s | 166 | 0.05 s | 101 | 30 |
| 64,000 | 2.57 s | 644 | 0.31 s | 145 | 48 |
| 333,878 | 188.02 s | 3,345 | 2.03 s | 207 | 93 |

Training time grew super-linearly with data (4x data → 18x time; 5.2x data → 73x time). Deduplication with
frequency weights: ~93x faster on the full set and a much smaller model.

## Isolation Forest diagnostic
- 4 of 20 features never vary among training normals: E2 (allocateBlock), E3 (PacketResponder terminating),
  E4 (Received block of size), unseen.
- Probe (one training block, then the same block + 5 unseen events):
  IF 0.7229 → 0.7229 (no change); PCA 96.85 → 196.85; OCSVM 30.26 → 42.64.
- Isolation Forest splits only on features that vary in its training data, so it is blind to these four.
  They are exactly the main HDFS anomaly signals: new templates (unseen) and missing write-completion
  events (E3, E4 absent in ~37% of anomalies). This explains its failure.
- Prediction for the live system: features such as latency and error rate always vary, so IF may perform
  much better there (to be tested in Phase 10).
- Note: the probe block (first training block) is itself unusual (PCA 96.8 vs threshold 2.2); the
  conclusion concerns the change in score, which is exactly zero for IF.

## Findings (RQ1, HDFS)
- One-Class SVM gives the best ranking (PR-AUC 0.999); no ML model beats the lookup table on F1.
- Methods that use relationships between counts (OCSVM, PCA) succeed; per-feature (z-score) and
  isolation-based (IF) methods fail, for explained reasons.
- Whether validation tuning helps depends on the model (helped OCSVM, hurt PCA on test).
- All working models flag the same 77 novel normal test blocks: candidates for error analysis (Day 18).

## Problems faced
- I first recorded "not feasible" for One-Class SVM without deduplication without measuring it. The measured
  timing showed full training takes 188 s on this data. The claim was replaced by the measured numbers.
  Lesson: every performance claim in the report must come from a measurement.
- Diagnostic cell was first placed above the cell that creates the models; moved to the end so that
  "Run All" works.