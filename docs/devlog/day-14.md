# Day 14 — Features, chronological split and baselines (HDFS)

## Done
- backend/detection/features/vectorizer.py: EventCountVectorizer (vocabulary from training data only,
  extra "unseen" column for templates not seen in training).
- backend/detection/evaluation/metrics.py: precision, recall, F1, FPR (anomaly = positive), PR-AUC, ROC-AUC.
- backend/detection/evaluation/splits.py: chronological train/validation/test split.
- tests/unit/test_vectorizer.py (7) and tests/unit/test_metrics.py (7).
- experiments/notebooks/03_hdfs_features_baselines.ipynb: split, features, recall ceiling, 4 baselines.
- experiments/results/hdfs_baselines.csv (committed); data/processed/hdfs_features.npz (not committed).

## Protocol
- Blocks ordered by first timestamp; 60% train / 20% validation / 20% test.
- Unsupervised models train on normal training blocks only (333,878); 11,158 training anomalies set aside.
- Vocabulary from training normals only; thresholds tuned on validation; test used for final results only.

## Results

| Split | Blocks | Anomalies | Anomaly % |
|---|---|---|---|
| train | 345,036 | 11,158 | 3.23 |
| validation | 115,012 | 4,001 | 3.48 |
| test | 115,013 | 1,679 | 1.46 |

- Training vocabulary: 19 of 53 templates -> 20 features. Normal blocks never contain unseen templates.
- Anomalies containing an unseen template: train 22.31%, validation 15.75%, test 43.24%.
- 207 distinct count vectors among training normal blocks.
- Recall ceiling: 0 validation/test anomalies identical to a training-normal vector -> 100%.

| Baseline | Val P | Val R | Val F1 | Test P | Test R | Test F1 | Test FP |
|---|---|---|---|---|---|---|---|
| B1 line count outside training range (13–298) | 1.000 | 0.230 | 0.374 | 1.000 | 0.615 | 0.762 | 0 |
| B2 contains unseen template | 1.000 | 0.158 | 0.272 | 1.000 | 0.432 | 0.604 | 0 |
| B3 B1 or B2 | 1.000 | 0.267 | 0.422 | 1.000 | 0.708 | 0.829 | 0 |
| B4 count vector never seen in training | 0.999 | 1.000 | 0.9996 | 0.956 | 1.000 | 0.978 | 77 |

## Findings
- HDFS v1 is close to solved by memorisation: a lookup table of normal count vectors reaches F1 0.978 on test.
- The lookup table does not generalise: false positives grow from 3 to 77 as new-but-normal patterns appear
  later in time. It also gives no score (no ranking or severity) and cannot work with continuous features.
- Anomaly rate and type drift over time (3.48% -> 1.46%; B1 recall 0.23 -> 0.62), so validation and test
  are reported separately.

## Consequences for the research
- On HDFS, ML models are compared against B4, with attention to false positives on new normal patterns
  (generalisation) and to graded scores.
- Model differences are expected to matter more on BGL and on the live system with continuous features.

## Problems faced
- None.