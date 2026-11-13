"""
Window-level anomaly detector for the live system (detection-design.md, Sections 3-5).

- Features: WindowFeatureExtractor (template counts + rates + latency + novelty), raw or log counts.
- Model: PCA or One-Class SVM, either one model for all services (global) or one per service.
- Threshold: label-free, 99.9th percentile of the scores of the (normal) training windows.
- Normalised score s in [0, 1], monotonic in the raw score, 0.5 at the threshold, and clamped so that
  s > 0.5 exactly when raw > threshold. Two formulas:
    "log_ratio" (default for PCA, whose scores are >= 0):
        raw <= threshold: s = 0.5 * raw / threshold
        raw >  threshold: s = 1 - 0.5 / (1 + log10(raw / threshold))      (10x -> 0.75, 100x -> 0.83)
      Keeps differences between strong anomalies visible; the exponential formula saturated at 1.0 for
      every real fault (Day 24).
    "exp" (One-Class SVM, whose scores can be negative):
        spread = threshold - median(training scores)
        raw <= threshold: s = 0.5 * exp((raw - threshold) / spread)
        raw >  threshold: s = 1 - 0.5 * exp(-(raw - threshold) / spread)
- Baselines: per service, the median log count and median p95 latency of the training windows. Used by
  severity grading (scoring/severity.py) to compare a window with that service's normal behaviour.

min_std is small (0.01) because live features include rates (normal error rate ~0.003) and latency.
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
MIN_THRESHOLD = 1e-12
JUST_ABOVE_HALF = float(np.nextafter(0.5, 1.0))
NORMALISATIONS = ("log_ratio", "exp")


def _clamp(raw: np.ndarray, threshold: np.ndarray, below: np.ndarray, above: np.ndarray) -> np.ndarray:
    flagged = raw > threshold
    return np.where(flagged, np.maximum(above, JUST_ABOVE_HALF), np.minimum(below, 0.5))


def normalise(raw: np.ndarray, threshold: np.ndarray, spread: np.ndarray) -> np.ndarray:
    """Exponential normalisation around the threshold (any score scale)."""
    raw = np.asarray(raw, float)
    threshold = np.asarray(threshold, float)
    z = (raw - threshold) / spread
    return _clamp(raw, threshold, 0.5 * np.exp(np.minimum(z, 0.0)), 1.0 - 0.5 * np.exp(-np.maximum(z, 0.0)))


def normalise_log_ratio(raw: np.ndarray, threshold: np.ndarray) -> np.ndarray:
    """Log-ratio normalisation for non-negative scores (PCA)."""
    raw = np.maximum(np.asarray(raw, float), 0.0)
    threshold = np.asarray(threshold, float)
    ratio = raw / np.maximum(threshold, MIN_THRESHOLD)
    below = 0.5 * np.minimum(ratio, 1.0)
    above = 1.0 - 0.5 / (1.0 + np.log10(np.maximum(ratio, 1.0)))
    return _clamp(raw, threshold, below, above)


class LiveDetector:
    def __init__(
        self,
        algorithm: str = "pca",
        log_counts: bool = False,
        per_service: bool = False,
        percentile: float = 99.9,
        min_std: float = 0.01,
        nu: float = 0.01,
        normalisation: str | None = None,
    ) -> None:
        if algorithm not in ("pca", "ocsvm"):
            raise ValueError("algorithm must be 'pca' or 'ocsvm'")
        normalisation = normalisation or ("log_ratio" if algorithm == "pca" else "exp")
        if normalisation not in NORMALISATIONS:
            raise ValueError(f"normalisation must be one of {NORMALISATIONS}")
        if normalisation == "log_ratio" and algorithm != "pca":
            raise ValueError("log_ratio normalisation needs non-negative scores (PCA)")
        self.algorithm = algorithm
        self.log_counts = log_counts
        self.per_service = per_service
        self.percentile = percentile
        self.min_std = min_std
        self.nu = nu
        self.normalisation = normalisation
        self.extractor: WindowFeatureExtractor | None = None
        self.models: dict[str, object] = {}
        self.thresholds: dict[str, float] = {}
        self.spreads: dict[str, float] = {}
        self.training_windows: dict[str, int] = {}
        self.baselines: dict[str, dict] = {}

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
        self.baselines = self._baselines(windows)
        return self

    @staticmethod
    def _baselines(windows: Sequence[WindowStats]) -> dict[str, dict]:
        baselines = {}
        for service in sorted({w.service for w in windows}):
            own = [w for w in windows if w.service == service]
            p95 = [float(np.percentile(w.latencies, 95)) for w in own if w.latencies]
            baselines[service] = {
                "log_count": float(np.median([w.log_count for w in own])),
                "p95_latency_ms": float(np.median(p95)) if p95 else None,
                "windows": len(own),
            }
        return baselines

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
        safe_threshold = np.where(known, threshold, 1.0)
        if getattr(self, "normalisation", "exp") == "log_ratio":       # older packages lack the attribute
            normalised = normalise_log_ratio(raw, safe_threshold)
        else:
            normalised = normalise(raw, safe_threshold, spread)
        # Services without a model (never seen in training) are not flagged and get score 0.
        score = np.where(known, normalised, 0.0)
        is_anomaly = known & (raw > threshold)
        return {"raw": raw, "threshold": threshold, "score": score, "is_anomaly": is_anomaly}