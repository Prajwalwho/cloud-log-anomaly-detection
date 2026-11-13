"""
Model package: everything the live detection service needs to score windows exactly as in training.

    <models_dir>/<name>-<version>/
        detector.joblib    LiveDetector (feature vocabulary, PCA model, threshold, spread)
        drain_state.bin    Drain parser state (templates and their ids), via drain3 file persistence
        metadata.json      configuration, masks, training data, evaluation results

The Drain state is essential: the model's feature columns are template ids. A fresh parser could assign
different ids to the same messages, putting every count in the wrong column. The state is loaded
read-only, so live parsing (which may discover new templates) never modifies a saved package.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import joblib
from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence

from .live_model import LiveDetector
from .preprocessing.parser import DEFAULT_DEPTH, DEFAULT_SIM_THRESHOLD, SERVICE_LOG_MASKS, create_template_miner

DETECTOR_FILE = "detector.joblib"
DRAIN_FILE = "drain_state.bin"
METADATA_FILE = "metadata.json"


def save_package(directory: Path, detector: LiveDetector, miner: TemplateMiner, metadata: dict) -> Path:
    """Write a new package. Refuses to overwrite: a version, once saved, never changes."""
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError(f"Model package {directory} already exists; use a new version")
    directory.mkdir(parents=True)
    joblib.dump(detector, directory / DETECTOR_FILE)

    snapshot = copy.deepcopy(miner)          # attach persistence to a copy, not to the caller's miner
    snapshot.persistence_handler = FilePersistence(str(directory / DRAIN_FILE))
    snapshot.save_state("model package")

    write_metadata(directory, metadata)
    return directory


def write_metadata(directory: Path, metadata: dict) -> None:
    (Path(directory) / METADATA_FILE).write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def load_package(directory: Path) -> tuple[LiveDetector, TemplateMiner, dict]:
    directory = Path(directory)
    metadata = json.loads((directory / METADATA_FILE).read_text(encoding="utf-8"))
    detector = joblib.load(directory / DETECTOR_FILE)

    masks = tuple(tuple(m) for m in metadata.get("parser", {}).get("masks", SERVICE_LOG_MASKS))
    miner = create_template_miner(
        sim_threshold=metadata.get("parser", {}).get("sim_threshold", DEFAULT_SIM_THRESHOLD),
        depth=metadata.get("parser", {}).get("depth", DEFAULT_DEPTH),
        masks=masks,
        persistence=FilePersistence(str(directory / DRAIN_FILE)),
    )
    miner.persistence_handler = None         # read-only: live parsing must never overwrite the package
    return detector, miner, metadata
