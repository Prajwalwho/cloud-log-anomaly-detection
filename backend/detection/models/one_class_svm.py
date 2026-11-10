"""
One-Class SVM detector.

Learns a boundary around normal data in a kernel (RBF) feature space. The anomaly score is how far a
point lies outside the boundary (negated decision function).

Training time grows roughly with the square of the number of samples, so training on hundreds of
thousands of sessions is infeasible. Log count vectors repeat heavily (HDFS: 333,878 normal training
blocks, only 207 distinct vectors), so with deduplicate=True the model is trained on the distinct
vectors, each weighted by how often it occurs. This keeps the information of the full data at a
fraction of the cost. Scoring also works on distinct rows and maps results back.
"""
from __future__ import annotations

import numpy as np
from sklearn.svm import OneClassSVM


class OneClassSVMDetector:
    name = "One-Class SVM"

    def __init__(self, nu: float = 0.01, min_std: float = 0.5, deduplicate: bool = True) -> None:
        if not 0 < nu <= 1:
            raise ValueError("nu must be in (0, 1]")
        self.nu = nu
        self.min_std = min_std
        self.deduplicate = deduplicate
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None
        self.model_: OneClassSVM | None = None
        self.n_training_rows_: int = 0

    def fit(self, X: np.ndarray) -> OneClassSVMDetector:
        X = np.asarray(X, dtype=float)
        self.mean_ = X.mean(axis=0)
        self.std_ = np.maximum(X.std(axis=0), self.min_std)
        Z = self._standardise(X)

        if self.deduplicate:
            rows, counts = np.unique(Z, axis=0, return_counts=True)
            weights = counts.astype(float)
        else:
            rows, weights = Z, None

        # gamma="auto" = 1 / n_features, appropriate for standardised features
        self.model_ = OneClassSVM(kernel="rbf", gamma="auto", nu=self.nu).fit(rows, sample_weight=weights)
        self.n_training_rows_ = len(rows)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Higher = more anomalous."""
        if self.model_ is None:
            raise RuntimeError("Call fit() before score()")
        Z = self._standardise(np.asarray(X, dtype=float))
        rows, inverse = np.unique(Z, axis=0, return_inverse=True)
        return -self.model_.decision_function(rows)[inverse.reshape(-1)]

    def _standardise(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean_) / self.std_