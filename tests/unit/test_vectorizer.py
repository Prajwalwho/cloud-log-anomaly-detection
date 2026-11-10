"""Unit tests for event-count vectors."""
import numpy as np
import pytest

from backend.detection.features.vectorizer import EventCountVectorizer, parse_events


def test_parse_events():
    assert parse_events("3 4 4 17") == [3, 4, 4, 17]
    assert parse_events("") == []


def test_counts_per_template():
    vectorizer = EventCountVectorizer(add_unseen_column=False).fit([[1, 2], [3]])
    matrix = vectorizer.transform([[1, 1, 2], [3, 3, 3]])
    assert vectorizer.feature_names == ["E1", "E2", "E3"]
    assert matrix.tolist() == [[2, 1, 0], [0, 0, 3]]


def test_unseen_templates_go_to_extra_column():
    vectorizer = EventCountVectorizer().fit([[1, 2]])
    matrix = vectorizer.transform([[1, 9, 9, 7]])
    assert vectorizer.feature_names == ["E1", "E2", "unseen"]
    assert matrix.tolist() == [[1, 0, 3]]


def test_vocabulary_comes_only_from_fit_data():
    vectorizer = EventCountVectorizer().fit([[5]])
    vectorizer.transform([[5, 6, 7]])
    assert list(vectorizer.vocabulary_) == [5]


def test_empty_sequence_gives_zero_row():
    vectorizer = EventCountVectorizer().fit([[1]])
    assert vectorizer.transform([[]]).tolist() == [[0, 0]]


def test_transform_before_fit_fails():
    with pytest.raises(RuntimeError):
        EventCountVectorizer().transform([[1]])


def test_output_is_integer_matrix():
    matrix = EventCountVectorizer().fit_transform([[1, 2], [2]])
    assert matrix.dtype == np.int32