# Day 19 — RQ2: feature representation and retraining

## Done
- experiments/run_rq2_features.py: same splits and test sets as RQ1; four variants; z-score, PCA,
  Isolation Forest, One-Class SVM (nu = 0.001); B5 FATAL count as BGL reference.
- experiments/results/rq2_feature_variants.csv.

## Variants
- V0 raw counts (RQ1 setting)
- V1 log(1 + count)
- V2 log counts + log level counts (FATAL, ERROR, SEVERE, WARNING, FAILURE) — BGL only
- V3 retrain on train + validation normal data, same test set, label-free threshold only
  (BGL: V2 features with vocabulary refit; HDFS: V1 features)

## Results — BGL (test)

| Model | V0 | V1 | V2 | V3 |
|---|---|---|---|---|
| PCA F1 label-free | 0.333 | 0.481 | 0.486 | 0.439 |
| One-Class SVM F1 label-free | 0.300 | 0.442 | 0.468 | 0.368 |
| z-score F1 label-free | 0.426 | 0.000 | 0.000 | 0.000 |
| Isolation Forest F1 label-free | 0.000 | 0.000 | 0.000 | 0.000 |
| PCA PR-AUC | 0.463 | 0.514 | 0.539 | 0.536 |
| One-Class SVM PR-AUC | 0.301 | 0.533 | 0.527 | 0.529 |
| z-score PR-AUC | 0.456 | 0.398 | 0.399 | 0.406 |
| Isolation Forest PR-AUC | 0.434 | 0.416 | 0.464 | 0.445 |

- Validation-tuned F1 (V0/V1/V2): OCSVM 0.285/0.386/0.356, PCA 0.279/0.340/0.294, z-score 0.245/0.275/0.275,
  IF 0.182/0.174/0.252.
- Reference B5 FATAL count: F1 label-free 0.000, validation-tuned 0.840, PR-AUC 0.726.
- Normal test windows with an unseen template: 73.73% (vocabulary from training normals) vs 66.19%
  (vocabulary from train + validation normals).

## Results — HDFS (test, control)

| Model | V0 | V1 | V3 |
|---|---|---|---|
| One-Class SVM F1 label-free | 0.971 | 0.956 | 0.956 |
| PCA F1 label-free | 0.965 | 0.803 | 0.803 |
| z-score F1 validation-tuned | 0.774 | 0.829 | — |
| One-Class SVM PR-AUC | 0.999 | 0.958 | 0.958 |
| PCA PR-AUC | 0.995 | 0.919 | 0.919 |
| Isolation Forest PR-AUC | 0.018 | 0.018 | 0.018 |

## Findings (RQ2)
- Representation matters, but in opposite directions per dataset:
  - BGL: log counts improved PCA and One-Class SVM (OCSVM PR-AUC 0.30 → 0.53; PCA F1 0.33 → 0.48). Raw counts
    are dominated by bursts (1–64,975 lines per window).
  - HDFS: log counts degraded them (PCA F1 0.965 → 0.803). Exact small counts are the signal (e.g. 3 vs 1–2
    "Received block" events); log scaling compresses those differences.
- z-score collapsed with log counts on BGL (0.426 → 0); its single-maximum score is sensitive to scaling.
  Not investigated further.
- Level features helped only slightly (PCA PR-AUC 0.514 → 0.539); ML models remain far below the
  validation-tuned FATAL-count rule (0.84).
- Retraining on train + validation reduced the unseen-template share of normal test windows only from 73.7% to
  66.2% and lowered F1 (PCA 0.486 → 0.439; OCSVM 0.468 → 0.368); ranking unchanged. New normal message types
  keep appearing during the test period, so a single retraining step does not counter BGL's drift.
- Isolation Forest stays at F1 0 (label-free) in every variant.

## Hypotheses checked
- Log scaling helps BGL: confirmed (for PCA, OCSVM); rejected for z-score.
- Level features move models toward the FATAL rule: weakly supported.
- Retraining on recent data counters drift: rejected.
- Variants keep HDFS near 0.97: rejected for log scaling (PCA 0.80); retraining neutral.

## Consequences for the live detector (Phase 6)
- No single representation is best; compare raw and log counts on the live system (Phase 10).
- Prefer label-free thresholds; drift requires continuous (not one-off) retraining or explicit handling of new
  templates.
- PCA and One-Class SVM are the candidate models; Isolation Forest only if continuous features change its behaviour.

## Limitations
- One chronological split and one random seed per experiment; variance not measured.
- The FATAL rule's 0.84 uses a validation-tuned threshold; label-free it scores 0.

## Problems faced
- None.