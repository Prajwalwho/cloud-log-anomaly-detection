"""
Time-ordered data splits.

Data must already be sorted by time (hdfs_sequences.csv is sorted by each block's first timestamp).
Earlier data is used for training, later data for validation and testing, as in real use: a detector
only ever knows the past. A random split would mix future data into training and overstate results.
"""
from __future__ import annotations

import numpy as np


def chronological_split(n: int, train: float = 0.6, validation: float = 0.2) -> dict[str, np.ndarray]:
    """Indices of consecutive train / validation / test parts (test gets the remainder)."""
    if not (0 < train < 1 and 0 < validation < 1 and train + validation < 1):
        raise ValueError("Fractions must be > 0 and train + validation < 1")
    train_end = int(n * train)
    validation_end = int(n * (train + validation))
    indices = np.arange(n)
    return {
        "train": indices[:train_end],
        "validation": indices[train_end:validation_end],
        "test": indices[validation_end:],
    }