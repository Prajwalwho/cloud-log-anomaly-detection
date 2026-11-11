"""
Window-level anomaly detector for the live system (detection-design.md, Sections 3-5).

- Features: WindowFeatureExtractor (template counts + rates + latency + novelty), raw or log counts.
- Model: PCA or One-Class SVM, either one model for all services (global) or one per service.
- Threshold: label-free, 99.9th percentile of the scores of the (normal) training windows.
- Normalised score s in [0, 1], monotonic in the raw score, 0.5 at the threshold:
      spread = threshold - median(training scores)
      raw <= threshold:  s = 0.5 * exp((raw - threshold) / spread)
      raw >  threshold:  s = 1 - 0.5 * exp(-(raw - threshold) / spread)
  This works for any score scale, including negative scores (One-Class SVM). The earlier formula
  raw / (raw + threshold) assumed non-negative scores and gave values above 1 for One-Class SVM.
  The flag is decided on the raw score (raw > threshold), and s is then clamped to the matching side of
  0.5, so "s > 0.5 exactly when flagged" holds even when rounding would put s at exactly 0.5.

min_std is small (0.01) because live features include rates (normal error rate ~0.003) and latency.
With the offline value 0.5, a jump of the error rate from 0 to 0.33 would look tiny after standardisation.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .evaluation.thresholds import percentile_threshold
from .features.extractor import WindowFeatureExtractor
from .models.one_class_svm import OneClassSVMDetector
from .models.pca import PCADetector
from .windowing import WindowStats

GLOBAL = "*"
MIN_SPREAD = 1e-9
JUST_ABOVE_HALF = float(np.nextafter(0.5, 1.0))


def normalise(raw: np.ndarray, threshold: np.ndarray, spread: np.ndarray) -> np.ndarray:
    """Map raw scores to [0, 1]: above 0.5 exactly when raw > threshold, at most 0.5 otherwise."""
    raw = np.asarray(raw, float)
    threshold = np.asarray(threshold, float)
    z = (raw - threshold) / spread
    below = 0.5 * np.exp(np.minimum(z, 0.0))
    above = 1.0 - 0.5 * np.exp(-np.maximum(z, 0.0))
    flagged = raw > threshold
    # Clamp to the correct side of 0.5 so floating-point rounding can never contradict the flag.
    return np.where(flagged, np.maximum(above, JUST_ABOVE_HALF), np.minimum(below, 0.5))


class LiveDetector:
    def __init__(
        self,
        algorithm: str = "pca",
        log_counts: bool = False,
        per_service: bool = False,
        percentile: float = 99.9,
        min_std: float = 0.01,
        nu: float = 0.01,
    ) -> None:
        if algorithm not in ("pca", "ocsvm"):
            raise ValueError("algorithm must be 'pca' or 'ocsvm'")
        self.algorithm = algorithm
        self.log_counts = log_counts
        self.per_service = per_service
        self.percentile = percentile
        self.min_std = min_std
        self.nu = nu
        self.extractor: WindowFeatureExtractor | None = None
        self.models: dict[str, object] = {}
        self.thresholds: dict[str, float] = {}
        self.spreads: dict[str, float] = {}
        self.training_windows: dict[str, int] = {}

    def _new_model(self):
        if self.algorithm == "pca":
            return PCADetector(variance=0.95, min_std=self.min_std)
        return OneClassSVMDetector(nu=self.nu, min_std=self.min_std)

    def _key(self, service: str) -> str:
        return service if self.per_service else GLOBAL

    def fit(self, windows: Sequence[WindowStats]) -> LiveDetector:
        if not windows:
            raise ValueError("No training windows")
        self.extractor = WindowFeatureExtractor(log_counts=self.log_counts).fit(windows)
        X = self.extractor.transform(windows)
        keys = np.array([self._key(w.service) for w in windows])
        for key in sorted(set(keys)):
            rows = np.flatnonzero(keys == key)
            model = self._new_model().fit(X[rows])
            scores = model.score(X[rows])
            threshold = percentile_threshold(scores, self.percentile)
            self.models[key] = model
            self.thresholds[key] = threshold
            self.spreads[key] = max(threshold - float(np.median(scores)), MIN_SPREAD)
            self.training_windows[key] = len(rows)
        return self

    def predict(self, windows: Sequence[WindowStats]) -> dict[str, np.ndarray]:
        """Raw score, threshold, normalised score (0..1) and anomaly flag for each window."""
        if self.extractor is None:
            raise RuntimeError("Call fit() first")
        X = self.extractor.transform(windows)
        raw = np.zeros(len(windows))
        threshold = np.full(len(windows), np.inf)
        spread = np.ones(len(windows))
        known = np.zeros(len(windows), dtype=bool)
        for key, model in self.models.items():
            rows = np.array([i for i, w in enumerate(windows) if self._key(w.service) == key], dtype=int)
            if rows.size:
                raw[rows] = model.score(X[rows])
                threshold[rows] = self.thresholds[key]
                spread[rows] = self.spreads[key]
                known[rows] = True
        # Services without a model (never seen in training) are not flagged and get score 0.
        score = np.where(known, normalise(raw, np.where(known, threshold, 0.0), spread), 0.0)
        is_anomaly = known & (raw > threshold)
        return {"raw": raw, "threshold": threshold, "score": score, "is_anomaly": is_anomaly}