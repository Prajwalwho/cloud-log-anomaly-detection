# Day 18 — BGL model comparison (RQ1)

## Done
- experiments/parse_bgl.py: further BGL masks after inspecting rare templates:
  DATE ("Mon Sep 26 14:05:33 2005"), MAC (colon-separated hex pairs), short NODE names (R30-M0, R22),
  IONODE (bglio71), all-letter 8+ hex values (fffffffc).
- experiments/run_bgl_comparison.py: complete BGL comparison as one script (windows, split, features,
  baselines, models, shared evaluation, summaries, PR curves, combined RQ1 table). Replaced the notebook
  version, which had become inconsistent through cell reordering.
- experiments/results/: bgl_model_comparison.csv, bgl_model_comparison_summary.csv, bgl_pr_curves.png,
  rq1_combined_summary.csv.

## Parser corrections
- Rare normal templates included node names, chip addresses and dates; the progress log showed ~1,700 templates
  created between lines 3.0 M and 3.5 M, caused by "Lustre mount FAILED : bglioNN ..." (one template per I/O node).
- After the new masks: 626 templates (was 2,672 / 2,845), steady growth, no jump.
- Updated template statistics (supersede day 17): 558 never alert (93 with ≤5 lines, genuinely different
  messages), 64 always alert, 4 mixed. Conclusion unchanged: templates almost determine labels.

## Setup
- 8,590 non-empty 15-minute windows, 858 anomalous (9.99%), median 12 lines.

| Split | Windows | Anomalous | % | Period |
|---|---|---|---|---|
| train | 5,154 | 592 | 11.49 | 2005-06-03 → 2005-10-10 |
| validation | 1,718 | 86 | 5.01 | 2005-10-10 → 2005-11-12 |
| test | 1,718 | 180 | 10.48 | 2005-11-12 → 2006-01-04 |

- 4,562 training normal windows; 2,444 distinct count vectors. 239 features (238 templates + unseen).
- Training normal window length: 1 to 64,975 lines (extremely skewed counts).

| Normal windows containing an unseen template | % |
|---|---|
| train | 0.00 |
| validation | 11.15 |
| test | 73.73 |

## Results (test)

| Model | F1 label-free p99.9 | F1 validation-tuned | PR-AUC |
|---|---|---|---|
| B5 FATAL count | 0.000 | 0.840 | 0.726 |
| z-score | 0.426 | 0.245 | 0.456 |
| PCA (59 of 239 components) | 0.333 | 0.279 | 0.463 |
| One-Class SVM (nu 0.001) | 0.300 | 0.285 | 0.301 |
| B2 unseen template | 0.241 | 0.258 | 0.460 |
| B4 lookup | 0.210 | 0.210 | 0.117 |
| B1 line count | 0.000 | 0.190 | 0.105 |
| Isolation Forest | 0.000 | 0.182 | 0.434 |

- One-Class SVM validation PR-AUC was ~0.168 for every nu (0.001–0.1): insensitive to tuning.
- Fit times < 1 s for all models.

## Predictions from day 17, checked
- "B2 unseen template will be very strong": wrong on test (precision 0.137). Correct on validation (recall 0.99,
  precision 0.32). Cause: new normal message types appear over time.
- "B4 lookup will be weak": correct (F1 0.21).
- "Isolation Forest will fail": mostly correct (F1 0 label-free), but PR-AUC 0.43, not random as on HDFS.

## Findings (RQ1)
- Strong concept drift on BGL: 73.7% of normal test windows contain message types unseen in training. All
  novelty-based methods (unseen rule, lookup, count-based ML models) produce many false positives.
- HDFS vs BGL: stable, repetitive behaviour (HDFS) gives F1 ≈ 0.97; drifting behaviour (BGL) gives 0.2–0.43
  for the same methods.
- The best BGL detector is a domain rule: number of FATAL lines per window with a validation-tuned threshold
  (F1 0.84, PR-AUC 0.73). Its label-free version fails because normal training windows can contain thousands
  of FATAL lines.
- Raw counts are extremely skewed (1–64,975 lines per window), which hurts z-score, PCA and OCSVM.
- Validation tuning is unreliable under drift: it helped FATAL count and hurt z-score on test.

## Next (RQ2, day 19)
- Log-scaled counts; level features (FATAL/ERROR counts) as model inputs; retraining on more recent normal data
  (train + validation) to measure the effect of drift.

## Problems faced
- Notebook cells were duplicated and run out of order (NameError chain). Replaced by a single script, which
  also makes the experiment reproducible with one command.
- Two more rounds of mask fixes were needed; each was found by inspecting rare templates and the progress log.