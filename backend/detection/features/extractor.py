"""
Live feature extraction for service windows (detection-design.md, Section 3).

Per window:
    template counts   one column per template seen during fit (the vocabulary), plus one "unseen" column
    log_count         number of log lines
    error_rate        ERROR/FATAL lines / log_count (0 for empty windows)
    warn_rate         WARN lines / log_count
    latency_mean_ms   mean latency of lines that carry latency (0 if none)
    latency_p95_ms    95th percentile latency (0 if none)
    new_templates     number of DISTINCT templates in the window that are not in the vocabulary

Counts (template counts, unseen, log_count) can be log-scaled with log1p. Offline research (RQ2) showed that
the best choice depends on the data (helps bursty BGL, hurts HDFS), so both are evaluated on live data.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from ..windowing import WindowStats

UNSEEN = "unseen"
EXTRA_FEATURES = ("log_count", "error_rate", "warn_rate", "latency_mean_ms", "latency_p95_ms", "new_templates")


class WindowFeatureExtractor:
    def __init__(self, log_counts: bool = False) -> None:
        self.log_counts = log_counts
        self.vocabulary_: list[int] | None = None
        self._index: dict[int, int] = {}

    def fit(self, windows: Iterable[WindowStats]) -> WindowFeatureExtractor:
        template_ids = sorted({tid for window in windows for tid in window.template_counts})
        self.vocabulary_ = template_ids
        self._index = {tid: column for column, tid in enumerate(template_ids)}
        return self

    def transform(self, windows: Sequence[WindowStats]) -> np.ndarray:
        if self.vocabulary_ is None:
            raise RuntimeError("Call fit() before transform()")
        n_templates = len(self.vocabulary_)
        matrix = np.zeros((len(windows), n_templates + 1 + len(EXTRA_FEATURES)))
        for row, window in enumerate(windows):
            matrix[row, : n_templates + 1] = self._template_columns(window)
            matrix[row, n_templates + 1:] = self._extra_columns(window)
        if self.log_counts:
            count_columns = list(range(n_templates + 1)) + [n_templates + 1]   # templates, unseen, log_count
            matrix[:, count_columns] = np.log1p(matrix[:, count_columns])
        return matrix

    def fit_transform(self, windows: Sequence[WindowStats]) -> np.ndarray:
        return self.fit(windows).transform(windows)

    @property
    def feature_names(self) -> list[str]:
        if self.vocabulary_ is None:
            raise RuntimeError("Call fit() first")
        return [f"E{tid}" for tid in self.vocabulary_] + [UNSEEN] + list(EXTRA_FEATURES)

    def summary(self, window: WindowStats) -> dict:
        """Human-readable window statistics (detection_windows columns in database-design.md)."""
        latencies = np.asarray(window.latencies)
        return {
            "log_count": window.log_count,
            "error_count": window.error_count,
            "warn_count": window.warn_count,
            "avg_latency_ms": float(latencies.mean()) if latencies.size else None,
            "p95_latency_ms": float(np.percentile(latencies, 95)) if latencies.size else None,
            "unique_templates": len(window.template_counts),
            "new_templates": sum(1 for tid in window.template_counts if tid not in self._index),
        }

    # ---------------- helpers ----------------
    def _template_columns(self, window: WindowStats) -> np.ndarray:
        columns = np.zeros(len(self.vocabulary_) + 1)
        for tid, count in window.template_counts.items():
            column = self._index.get(tid)
            columns[column if column is not None else -1] += count
        return columns

    def _extra_columns(self, window: WindowStats) -> list[float]:
        n = window.log_count
        latencies = np.asarray(window.latencies)
        return [
            float(n),
            window.error_count / n if n else 0.0,
            window.warn_count / n if n else 0.0,
            float(latencies.mean()) if latencies.size else 0.0,
            float(np.percentile(latencies, 95)) if latencies.size else 0.0,
            float(sum(1 for tid in window.template_counts if tid not in self._index)),
        ]