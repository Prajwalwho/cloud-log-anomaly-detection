"""
Common evaluation of anomaly scores, so every model is measured in exactly the same way.

For each model:
- thresholds: label-free p99.9 of normal training scores, and validation-tuned best F1;
- per split: precision, recall, F1, FP, FN, PR-AUC, ROC-AUC;
- optionally: how many "novel normal" sessions are flagged (normal sessions whose exact
  feature vector never appeared in training) - a test of generalisation.
"""
from __future__ import annotations

import numpy as np

from .metrics import binary_metrics, ranking_metrics
from .thresholds import best_f1_threshold, percentile_threshold, predict


def thresholds_for(scores: np.ndarray, y: np.ndarray, train_normal: np.ndarray,
                   validation: np.ndarray) -> dict[str, float]:
    return {
        "label-free p99.9": percentile_threshold(scores[train_normal], 99.9),
        "validation-tuned": best_f1_threshold(y[validation], scores[validation])[0],
    }


def evaluate_scores(
    model: str,
    scores: np.ndarray,
    y: np.ndarray,
    train_normal: np.ndarray,
    splits: dict[str, np.ndarray],
    novel: np.ndarray | None = None,
) -> list[dict]:
    """One row per (threshold, split). `splits` must contain a "validation" entry."""
    scores = np.asarray(scores, dtype=float)
    rows = []
    for threshold_name, threshold in thresholds_for(scores, y, train_normal, splits["validation"]).items():
        flagged = predict(scores, threshold)
        for split_name, idx in splits.items():
            m = binary_metrics(y[idx], flagged[idx])
            ranking = ranking_metrics(y[idx], scores[idx])
            row = {
                "model": model, "threshold": threshold_name, "value": threshold, "split": split_name,
                "precision": m.precision, "recall": m.recall, "f1": m.f1, "fp": m.fp, "fn": m.fn,
                "pr_auc": ranking["pr_auc"], "roc_auc": ranking["roc_auc"],
            }
            if novel is not None:
                novel_normal = idx[novel[idx] & ~y[idx]]
                row["novel_normal_flagged"] = int(flagged[novel_normal].sum())
                row["novel_normal_total"] = len(novel_normal)
            rows.append(row)
    return rows