# Day 15 — Statistical baseline and PCA (HDFS)

## Done
- backend/detection/models/statistical.py: ZScoreDetector (largest absolute z-score, minimum std for
  constant features).
- backend/detection/models/pca.py: PCADetector (standardisation, PCA with 95% variance, squared prediction
  error as score).
- backend/detection/evaluation/thresholds.py: label-free percentile threshold, validation-tuned best-F1
  threshold, common rule "anomaly if score > threshold".
- tests/unit/test_models.py: 7 tests.
- experiments/notebooks/04_hdfs_statistical_pca.ipynb; experiments/results/hdfs_statistical_pca.csv.

## Results
- Training: z-score 0.05 s, PCA 0.23 s on 333,878 normal blocks; scoring 575k blocks < 0.2 s.
- PCA keeps 5 of 20 components.

| Model | Val PR-AUC | Test PR-AUC | Test ROC-AUC |
|---|---|---|---|
| z-score | 0.547 | 0.756 | 0.874 |
| PCA | 0.995 | 0.995 | 0.9999 |

| Model | Threshold | Val F1 | Test P | Test R | Test F1 | Test FP | Novel normal flagged (test) |
|---|---|---|---|---|---|---|---|
| z-score | label-free p99.9 | 0.013 | 0.286 | 0.001 | 0.002 | 5 | 0/77 |
| z-score | validation-tuned | 0.619 | 0.783 | 0.765 | 0.774 | 356 | 0/77 |
| PCA | label-free p99.9 | 0.943 | 0.952 | 0.977 | 0.965 | 82 | 77/77 |
| PCA | validation-tuned | 0.986 | 0.923 | 1.000 | 0.960 | 140 | 77/77 |
| z-score / PCA | label-free max | ~0.01 | — | ~0.001 | ~0.002 | 0 | 0/77 |
| B4 lookup (Day 14) | — | 0.9996 | 0.956 | 1.000 | 0.978 | 77 | 77/77 |

## Findings
- HDFS anomalies break relationships between event counts rather than making a single count extreme:
  PCA (relationships) ranks almost perfectly, z-score (one feature at a time) does not.
- Label-free p99.9 generalised better to test than the validation-tuned threshold, because the anomaly mix
  drifts between validation and test. Argument for label-free thresholds in the live system.
- The maximum training score is not a usable threshold: a few extreme training-normal blocks (possibly
  mislabelled) push it far above typical anomaly scores. High percentiles are robust to this.
- PCA nearly matches the lookup table on F1 (0.965 vs 0.978) and adds a graded score, but also flags all
  77 novel normal blocks. These blocks break normal count relationships; inspect them in error analysis.

## Problems faced
- None.