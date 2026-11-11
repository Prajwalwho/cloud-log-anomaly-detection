"""Unit tests for the live window detector."""
import numpy as np
import pytest

from backend.detection.live_model import LiveDetector, normalise
from backend.detection.windowing import WindowStats

rng = np.random.default_rng(3)


def window(service: str, logs: int, errors: int = 0, template: int = 1) -> WindowStats:
    w = WindowStats(service, 0.0, 60.0)
    for i in range(logs):
        w.add("ERROR" if i < errors else "INFO", template, 50.0 + rng.normal(0, 2))
    return w


def normal_windows(service: str, n: int = 200) -> list[WindowStats]:
    return [window(service, int(rng.integers(90, 110))) for _ in range(n)]


@pytest.mark.parametrize("algorithm", ["pca", "ocsvm"])
@pytest.mark.parametrize("per_service", [False, True])
def test_error_burst_window_is_flagged(algorithm, per_service):
    training = normal_windows("a") + normal_windows("b")
    detector = LiveDetector(algorithm=algorithm, per_service=per_service).fit(training)
    result = detector.predict([window("a", 100, errors=40), window("a", 100)])
    assert result["is_anomaly"][0]
    assert result["score"][0] > result["score"][1]


def test_new_template_is_flagged():
    detector = LiveDetector().fit(normal_windows("a"))
    assert detector.predict([window("a", 100, template=99)])["is_anomaly"][0]


@pytest.mark.parametrize("algorithm", ["pca", "ocsvm"])
def test_normalised_score_properties(algorithm):
    detector = LiveDetector(algorithm=algorithm).fit(normal_windows("a"))
    result = detector.predict(normal_windows("a", 30) + [window("a", 100, errors=40)])
    score = result["score"]
    assert np.all((score >= 0) & (score <= 1))
    assert np.all((score > 0.5) == result["is_anomaly"])
    order = np.argsort(result["raw"])
    assert np.all(np.diff(score[order]) >= 0)          # monotonic in the raw score


def test_normalise_is_half_at_threshold_and_bounded():
    s = normalise(np.array([-100.0, 2.0, 1e6]), threshold=np.array([2.0] * 3), spread=np.array([1.0] * 3))
    assert s[1] == pytest.approx(0.5)
    assert 0 <= s[0] < 0.5 < s[2] <= 1


def test_per_service_keeps_separate_thresholds():
    detector = LiveDetector(per_service=True).fit(normal_windows("a") + normal_windows("b"))
    assert set(detector.thresholds) == {"a", "b"}


def test_unknown_service_is_not_flagged():
    detector = LiveDetector(per_service=True).fit(normal_windows("a"))
    result = detector.predict([window("zzz", 100, errors=50)])
    assert not result["is_anomaly"][0] and result["score"][0] == 0.0