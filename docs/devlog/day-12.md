# Day 12 — HDFS dataset and exploration (Phase 5 starts)

## Done
- Downloaded HDFS v1 from LogHub (Zenodo record 8196385) into data/raw/HDFS_v1 (not committed).
- docs/research/research-plan.md: research questions RQ1–RQ4, datasets, offline and live evaluation method,
  threats to validity, references with verification status.
- experiments/notebooks/01_hdfs_exploration.ipynb: one streaming pass over the raw log (levels, components,
  block ids, time span), labels, lines per block for normal vs anomalous blocks.
- data/processed/hdfs_block_stats.csv (not committed).

## Results
- (paste the numbers from the Findings cell)

## Decisions
- Own parsing with Drain instead of LogHub's pre-processed files, so the full pipeline is reproducible
  and explainable.
- Session = block id (the unit the labels refer to).

## Problems faced
- (note anything you hit)