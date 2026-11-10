"""
Detection metrics. The anomaly class is the positive class.

With rare anomalies (2.9% in HDFS) accuracy is meaningless: predicting "normal" for everything scores
97% accuracy and detects nothing. We therefore report precision, recall and F1 for the anomaly class,
the false positive rate, and threshold-free ranking metrics (PR-AUC, ROC-AUC).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


@dataclass(frozen=True)
class DetectionMetrics:
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float   # of the blocks flagged, how many were real anomalies
    recall: float      # of the real anomalies, how many were flagged
    f1: float          # harmonic mean of precision and recall
    fpr: float         # share of normal blocks wrongly flagged

    def as_dict(self) -> dict:
        return asdict(self)


def binary_metrics(y_true, y_pred) -> DetectionMetrics:
    """Metrics for hard predictions (True = anomaly). Undefined ratios (0/0) are reported as 0."""
    y_true = np.asarray(y_true, dtype=bool)
    y_pred = np.asarray(y_pred, dtype=bool)
    if y_true.shape != y_pred.shape:
        raise ValueError(f"Shape mismatch: {y_true.shape} vs {y_pred.shape}")

    tp = int(np.sum(y_true & y_pred))
    fp = int(np.sum(~y_true & y_pred))
    fn = int(np.sum(y_true & ~y_pred))
    tn = int(np.sum(~y_true & ~y_pred))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return DetectionMetrics(tp, fp, fn, tn, precision, recall, f1, fpr)


def ranking_metrics(y_true, scores) -> dict[str, float]:
    """Threshold-free metrics for anomaly scores (higher = more anomalous)."""
    y_true = np.asarray(y_true, dtype=bool)
    if y_true.all() or not y_true.any():
        raise ValueError("Ranking metrics need both normal and anomalous examples")
    return {
        "pr_auc": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
    }