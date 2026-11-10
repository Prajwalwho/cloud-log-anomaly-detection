"""Unit tests for Isolation Forest, One-Class SVM and the common evaluation."""
import numpy as np

from backend.detection.evaluation.evaluate import evaluate_scores
from backend.detection.models.isolation_forest import IsolationForestDetector
from backend.detection.models.one_class_svm import OneClassSVMDetector

rng = np.random.default_rng(1)


def normal_data(n: int = 400) -> np.ndarray:
    a = rng.integers(1, 4, size=n)
    return np.column_stack([a, a, np.zeros(n)]).astype(float)


OUTLIER = np.array([[3.0, 0.0, 4.0]])
TYPICAL = np.array([[2.0, 2.0, 0.0]])


def test_isolation_forest_scores_outlier_higher():
    model = IsolationForestDetector(n_estimators=100).fit(normal_data())
    assert model.score(OUTLIER)[0] > model.score(TYPICAL)[0]


def test_one_class_svm_scores_outlier_higher():
    model = OneClassSVMDetector(nu=0.05).fit(normal_data())
    assert model.score(OUTLIER)[0] > model.score(TYPICAL)[0]


def test_one_class_svm_trains_on_distinct_rows():
    data = normal_data()
    model = OneClassSVMDetector().fit(data)
    assert model.n_training_rows_ == len(np.unique(data, axis=0))
    assert model.n_training_rows_ < len(data)


def test_deduplicated_and_full_training_agree_on_the_outlier():
    data = normal_data()
    points = np.vstack([TYPICAL, OUTLIER])
    for deduplicate in (True, False):
        scores = OneClassSVMDetector(nu=0.05, deduplicate=deduplicate).fit(data).score(points)
        assert scores[1] > scores[0]


def test_score_preserves_row_order():
    model = OneClassSVMDetector(nu=0.05).fit(normal_data())
    points = np.vstack([OUTLIER, TYPICAL, OUTLIER])
    scores = model.score(points)
    assert scores[0] == scores[2] and scores[0] > scores[1]


def test_evaluate_scores_on_separable_data():
    y = np.array([False] * 8 + [True] * 2 + [False] * 8 + [True] * 2)
    scores = np.where(y, 10.0, 1.0) + np.arange(len(y)) * 1e-3
    splits = {"validation": np.arange(10), "test": np.arange(10, 20)}
    rows = evaluate_scores("toy", scores, y, train_normal=np.arange(8), splits=splits)
    tuned_test = next(r for r in rows if r["threshold"] == "validation-tuned" and r["split"] == "test")
    assert tuned_test["f1"] == 1.0
    assert {"precision", "recall", "pr_auc", "roc_auc"} <= tuned_test.keys()