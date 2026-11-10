"""Unit tests for the z-score and PCA detectors and threshold selection."""
import numpy as np
import pytest

from backend.detection.evaluation.metrics import binary_metrics
from backend.detection.evaluation.thresholds import best_f1_threshold, percentile_threshold, predict
from backend.detection.models.pca import PCADetector
from backend.detection.models.statistical import ZScoreDetector

rng = np.random.default_rng(0)


def normal_data(n: int = 500) -> np.ndarray:
    """Normal sessions: feature 1 always equals feature 0, feature 2 is always 0."""
    a = rng.integers(1, 5, size=n)
    return np.column_stack([a, a, np.zeros(n)]).astype(float)


def test_zscore_scores_outliers_higher():
    model = ZScoreDetector().fit(normal_data())
    scores = model.score(np.array([[2, 2, 0], [2, 2, 5]], dtype=float))
    assert scores[1] > scores[0]


def test_zscore_handles_constant_features():
    model = ZScoreDetector(min_std=0.5).fit(normal_data())
    assert np.isfinite(model.score(np.array([[2, 2, 1]], dtype=float))).all()


def test_pca_flags_points_outside_the_normal_subspace():
    model = PCADetector(variance=0.9).fit(normal_data())
    in_subspace = model.score(np.array([[3, 3, 0]], dtype=float))[0]
    off_subspace = model.score(np.array([[3, 0, 0]], dtype=float))[0]   # breaks "feature 1 = feature 0"
    assert off_subspace > 10 * max(in_subspace, 1e-9)


def test_models_must_be_fitted_first():
    with pytest.raises(RuntimeError):
        ZScoreDetector().score(np.zeros((1, 3)))
    with pytest.raises(RuntimeError):
        PCADetector().score(np.zeros((1, 3)))


def test_percentile_100_is_the_maximum():
    assert percentile_threshold(np.array([1.0, 5.0, 3.0]), 100) == 5.0


def test_best_f1_threshold_separates_clean_data():
    y = np.array([0, 0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    threshold, f1 = best_f1_threshold(y, scores)
    assert f1 == pytest.approx(1.0)
    assert binary_metrics(y, predict(scores, threshold)).f1 == pytest.approx(1.0)


def test_threshold_rule_is_strictly_greater():
    assert predict(np.array([1.0, 2.0]), 1.0).tolist() == [False, True]