"""Unit tests for live window features."""
import numpy as np
import pytest

from backend.detection.features.extractor import EXTRA_FEATURES, WindowFeatureExtractor
from backend.detection.windowing import WindowStats


def window(counts: dict, errors: int = 0, warns: int = 0, latencies=()) -> WindowStats:
    w = WindowStats("svc", 0.0, 60.0)
    for tid, n in counts.items():
        for _ in range(n):
            w.add("INFO", tid, None)
    w.error_count, w.warn_count = errors, warns
    w.latencies = list(latencies)
    return w


def test_vocabulary_and_feature_names():
    ext = WindowFeatureExtractor().fit([window({1: 2, 3: 1})])
    assert ext.vocabulary_ == [1, 3]
    assert ext.feature_names == ["E1", "E3", "unseen", *EXTRA_FEATURES]


def test_counts_unseen_and_new_templates():
    ext = WindowFeatureExtractor().fit([window({1: 1})])
    row = ext.transform([window({1: 2, 5: 3, 6: 1})])[0]
    names = ext.feature_names
    assert row[names.index("E1")] == 2
    assert row[names.index("unseen")] == 4
    assert row[names.index("new_templates")] == 2
    assert row[names.index("log_count")] == 6


def test_rates_and_latency():
    ext = WindowFeatureExtractor().fit([window({1: 1})])
    row = ext.transform([window({1: 4}, errors=1, warns=2, latencies=[10, 20, 30, 40])])[0]
    names = ext.feature_names
    assert row[names.index("error_rate")] == pytest.approx(0.25)
    assert row[names.index("warn_rate")] == pytest.approx(0.5)
    assert row[names.index("latency_mean_ms")] == pytest.approx(25)


def test_empty_window_gives_zeros_without_errors():
    ext = WindowFeatureExtractor().fit([window({1: 1})])
    assert np.all(ext.transform([WindowStats("svc", 0.0, 60.0)]) == 0)


def test_log_counts_option_scales_counts_only():
    ext = WindowFeatureExtractor(log_counts=True).fit([window({1: 1})])
    row = ext.transform([window({1: 3}, errors=3)])[0]
    names = ext.feature_names
    assert row[names.index("E1")] == pytest.approx(np.log1p(3))
    assert row[names.index("log_count")] == pytest.approx(np.log1p(3))
    assert row[names.index("error_rate")] == pytest.approx(1.0)


def test_transform_before_fit_fails():
    with pytest.raises(RuntimeError):
        WindowFeatureExtractor().transform([window({1: 1})])