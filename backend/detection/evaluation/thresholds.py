"""
Turning anomaly scores into decisions. Rule everywhere: anomaly if score > threshold.

Two ways to choose a threshold, neither using test labels:
- label-free: a high percentile of the scores of NORMAL TRAINING sessions. percentile=100 is the
  highest training score (no false alarms on training data). Needs no labels: realistic deployment.
- validation-tuned: the threshold with the best F1 on the labelled VALIDATION split. Shows the best
  achievable trade-off when some labels exist; reported separately from the label-free result.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import precision_recall_curve


def percentile_threshold(normal_scores: np.ndarray, percentile: float = 99.9) -> float:
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be in (0, 100]")
    return float(np.percentile(np.asarray(normal_scores, dtype=float), percentile))


def best_f1_threshold(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Threshold maximising F1 on labelled data. Returns (threshold, f1)."""
    precision, recall, thresholds = precision_recall_curve(np.asarray(y_true, dtype=bool), scores)
    with np.errstate(divide="ignore", invalid="ignore"):
        f1 = np.where(precision + recall > 0, 2 * precision * recall / (precision + recall), 0.0)
    best = int(np.argmax(f1[:-1]))        # the last point (recall 0) has no threshold
    # precision_recall_curve flags score >= threshold; convert to the "score > threshold" rule
    return float(np.nextafter(thresholds[best], -np.inf)), float(f1[best])


def predict(scores: np.ndarray, threshold: float) -> np.ndarray:
    return np.asarray(scores) > threshold