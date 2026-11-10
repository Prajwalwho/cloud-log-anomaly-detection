"""
Isolation Forest detector.

Builds many random trees that split the data at random feature values. Points in dense (normal)
regions need many splits to be isolated; anomalies are isolated after only a few. The anomaly score
is derived from the average path length: shorter path = easier to isolate = more anomalous.

Trained on normal data only (novelty detection). Fast and suitable for large datasets because each
tree sees only a small random sample (max_samples).
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest


class IsolationForestDetector:
    name = "Isolation Forest"

    def __init__(self, n_estimators: int = 200, max_samples: int | str = 256, random_state: int = 42) -> None:
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state
        self.model_: IsolationForest | None = None

    def fit(self, X: np.ndarray) -> IsolationForestDetector:
        self.model_ = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1,
        ).fit(np.asarray(X, dtype=float))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Higher = more anomalous (negated sklearn score_samples)."""
        if self.model_ is None:
            raise RuntimeError("Call fit() before score()")
        return -self.model_.score_samples(np.asarray(X, dtype=float))