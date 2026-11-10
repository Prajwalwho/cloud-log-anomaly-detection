"""
Event-count vectors: the standard representation for count-based log anomaly detection.

Each session (an HDFS block, or a time window) becomes a vector with one column per log template,
holding how often that template occurred. Order is ignored on purpose: parallel operations interleave
their log lines, so order varies a lot between otherwise identical sessions.

The vocabulary (which templates get a column) is learned in fit() from TRAINING data only.
Templates never seen in training are counted together in one extra "unseen" column, so novelty at
test time is visible to the models without leaking any information from the test data.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

UNSEEN = "unseen"


def parse_events(events: str) -> list[int]:
    """'3 4 4 17' -> [3, 4, 4, 17] (format of the events column in hdfs_sequences.csv)."""
    return [int(token) for token in str(events).split()] if isinstance(events, str) and events else []


class EventCountVectorizer:
    def __init__(self, add_unseen_column: bool = True) -> None:
        self.add_unseen_column = add_unseen_column
        self.vocabulary_: dict[int, int] | None = None   # template id -> column index

    def fit(self, sequences: Iterable[Sequence[int]]) -> EventCountVectorizer:
        template_ids = sorted({template_id for sequence in sequences for template_id in sequence})
        self.vocabulary_ = {template_id: column for column, template_id in enumerate(template_ids)}
        return self

    def transform(self, sequences: Iterable[Sequence[int]]) -> np.ndarray:
        if self.vocabulary_ is None:
            raise RuntimeError("Call fit() before transform()")
        sequences = list(sequences)
        n_columns = len(self.vocabulary_) + (1 if self.add_unseen_column else 0)
        matrix = np.zeros((len(sequences), n_columns), dtype=np.int32)
        unseen_column = len(self.vocabulary_)
        for row, sequence in enumerate(sequences):
            for template_id in sequence:
                column = self.vocabulary_.get(template_id)
                if column is not None:
                    matrix[row, column] += 1
                elif self.add_unseen_column:
                    matrix[row, unseen_column] += 1
        return matrix

    def fit_transform(self, sequences: Sequence[Sequence[int]]) -> np.ndarray:
        return self.fit(sequences).transform(sequences)

    @property
    def feature_names(self) -> list[str]:
        if self.vocabulary_ is None:
            raise RuntimeError("Call fit() first")
        names = [f"E{template_id}" for template_id in self.vocabulary_]
        return names + ([UNSEEN] if self.add_unseen_column else [])