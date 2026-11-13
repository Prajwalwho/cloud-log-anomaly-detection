"""Unit tests for model packages."""
import numpy as np
import pytest

from backend.detection.live_model import LiveDetector
from backend.detection.package import DRAIN_FILE, load_package, save_package
from backend.detection.preprocessing.parser import SERVICE_LOG_MASKS, create_template_miner
from backend.detection.windowing import WindowStats

MESSAGES = [
    "Token validated for user u6601",
    "Order 845970 created for user u6601 with 5 items",
    "Payment txn_c9731bc4b8 processed for order 845970: amount 4163.57 INR",
]
rng = np.random.default_rng(5)


def trained(tmp_path):
    miner = create_template_miner(masks=SERVICE_LOG_MASKS)
    ids = [miner.add_log_message(m)["cluster_id"] for m in MESSAGES]
    windows = []
    for _ in range(100):
        w = WindowStats("svc", 0.0, 60.0)
        for tid in ids:
            for _ in range(int(rng.integers(5, 10))):
                w.add("INFO", tid, 50.0 + rng.normal(0, 2))
        windows.append(w)
    detector = LiveDetector(log_counts=True).fit(windows)
    metadata = {"name": "test", "parser": {"masks": [list(m) for m in SERVICE_LOG_MASKS]}}
    path = save_package(tmp_path / "pkg", detector, miner, metadata)
    return path, detector, ids, windows


def test_round_trip_keeps_template_ids_and_scores(tmp_path):
    path, detector, ids, windows = trained(tmp_path)
    loaded_detector, loaded_miner, metadata = load_package(path)
    assert [loaded_miner.add_log_message(m)["cluster_id"] for m in MESSAGES] == ids
    assert np.allclose(loaded_detector.predict(windows)["raw"], detector.predict(windows)["raw"])
    assert metadata["name"] == "test"


def test_existing_package_is_not_overwritten(tmp_path):
    path, detector, _, _ = trained(tmp_path)
    with pytest.raises(FileExistsError):
        save_package(path, detector, create_template_miner(), {})


def test_loaded_parser_never_writes_to_the_package(tmp_path):
    path, _, _, _ = trained(tmp_path)
    before = (path / DRAIN_FILE).read_bytes()
    _, miner, _ = load_package(path)
    for i in range(50):
        miner.add_log_message(f"Completely new message type number {i} appeared")
    assert miner.persistence_handler is None
    assert (path / DRAIN_FILE).read_bytes() == before