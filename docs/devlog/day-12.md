# Day 12 — HDFS dataset and exploration (Phase 5 starts)

## Done
- Downloaded HDFS v1 from LogHub (Zenodo record 8196385, zip 186,645,559 bytes) into data/raw/HDFS_v1
  (not committed). Contents: HDFS.log (1.58 GB) and preprocessed/ (anomaly_label.csv, templates,
  event matrices).
- docs/research/research-plan.md: research questions RQ1–RQ4, datasets, offline and live evaluation method,
  threats to validity, references with verification status.
- experiments/notebooks/01_hdfs_exploration.ipynb: one streaming pass over the raw log (89 s),
  labels, lines per block for normal vs anomalous blocks, distribution plot.
- data/processed/hdfs_block_stats.csv (not committed).

## Results

| Property | Value |
|---|---|
| Lines | 11,175,629 (0 unparsed) |
| Time span | 2008-11-09 20:35:18 → 2008-11-11 11:16:28 (38.7 h) |
| Levels | INFO 96.75%, WARN 3.25%, no ERROR/FATAL |
| Lines with exactly one block id | 100% |
| Blocks (sessions) | 575,061, all labelled |
| Anomalous blocks | 16,838 (2.93%) |

| Lines per block | Normal | Anomaly |
|---|---|---|
| min | 13 | 2 |
| 25th percentile | 19 | 4 |
| median | 19 | 20 |
| mean | 19.5 | 17.1 |
| std | 4.8 | 12.4 |
| max | 298 | 284 |

Top components: dfs.FSNamesystem (3.70 M), DataNode$PacketResponder (3.41 M), DataNode$DataXceiver (2.52 M),
FSDataset (1.41 M).

## Findings
- No ERROR level exists: HDFS anomalies are not visible from log levels, only from which events occur
  (and in which order). Template extraction and event-count features are required.
- Sessions are clean: every line belongs to exactly one block.
- Anomalies form two groups: truncated sessions (≤4 lines for at least 25% of anomalies; normal blocks never
  have fewer than 13 lines) and sessions of normal length that differ only in content.
- Strong class imbalance (2.93%): accuracy is meaningless; metrics will be precision, recall and F1 for the
  anomaly class, plus PR-AUC.

## Decisions
- Own parsing with Drain instead of LogHub's pre-processed files, so the full pipeline is reproducible
  and explainable. The provided HDFS.log_templates.csv is used only to cross-check our parser.
- Session = block id (the unit the labels refer to).
- A simple line-count rule ("fewer than 13 lines = anomaly") will be included as a baseline; ML models
  must outperform it to justify their complexity.

## Problems faced
- None.