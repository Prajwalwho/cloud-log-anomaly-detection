"""
Statistical baseline: per-feature z-scores against normal training data.

For each feature (template count) the mean and standard deviation over normal training
sessions are learned. A session's anomaly score is its largest absolute z-score:
"how many standard deviations is the most unusual feature away from normal?"

Many features are constant in normal data (std = 0), e.g. the "unseen" column. A minimum
standard deviation (min_std) keeps scores finite: one unexpected occurrence of such a template
then scores 1 / min_std.
"""
from __future__ import annotations

import numpy as np


class ZScoreDetector:
    name = "z-score"

    def __init__(self, min_std: float = 0.5) -> None:
        if min_std <= 0:
            raise ValueError("min_std must be positive")
        self.min_std = min_std
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> ZScoreDetector:
        X = np.asarray(X, dtype=float)
        self.mean_ = X.mean(axis=0)
        self.std_ = np.maximum(X.std(axis=0), self.min_std)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Higher = more anomalous."""
        if self.mean_ is None:
            raise RuntimeError("Call fit() before score()")
        z = np.abs((np.asarray(X, dtype=float) - self.mean_) / self.std_)
        return z.max(axis=1)