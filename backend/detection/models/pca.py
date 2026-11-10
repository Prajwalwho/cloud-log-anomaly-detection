"""
PCA anomaly detector (subspace method), the classic approach for event-count vectors in
log anomaly detection.

1. Standardise features with the mean / std of normal training data.
2. Fit PCA on normal training data. The first components, which explain `variance`
   (default 95%) of the variance, span the "normal subspace": the typical ways in which
   normal sessions differ from each other.
3. Score = squared prediction error (SPE): the squared distance of a session from the normal
   subspace, i.e. the part of the session that normal behaviour cannot explain.
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA


class PCADetector:
    name = "PCA"

    def __init__(self, variance: float = 0.95, min_std: float = 0.5) -> None:
        if not 0 < variance < 1:
            raise ValueError("variance must be between 0 and 1")
        self.variance = variance
        self.min_std = min_std
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None
        self.pca_: PCA | None = None

    def fit(self, X: np.ndarray) -> PCADetector:
        X = np.asarray(X, dtype=float)
        self.mean_ = X.mean(axis=0)
        self.std_ = np.maximum(X.std(axis=0), self.min_std)
        self.pca_ = PCA(n_components=self.variance, svd_solver="full").fit(self._standardise(X))
        return self

    @property
    def n_components_(self) -> int:
        if self.pca_ is None:
            raise RuntimeError("Call fit() first")
        return int(self.pca_.n_components_)

    def score(self, X: np.ndarray) -> np.ndarray:
        """Squared prediction error. Higher = more anomalous."""
        if self.pca_ is None:
            raise RuntimeError("Call fit() before score()")
        Z = self._standardise(np.asarray(X, dtype=float))
        reconstructed = self.pca_.inverse_transform(self.pca_.transform(Z))
        return ((Z - reconstructed) ** 2).sum(axis=1)

    def _standardise(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean_) / self.std_