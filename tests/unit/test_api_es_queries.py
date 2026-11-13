"""Log documents are returned in the contract format."""
from backend.api.app.es_queries import normalise_timestamp, to_log_event


def test_six_decimal_timestamps_are_normalised_to_milliseconds():
    assert normalise_timestamp("2026-11-13T12:11:53.074000Z") == "2026-11-13T12:11:53.074Z"
    assert normalise_timestamp("2026-11-13T12:11:53.074Z") == "2026-11-13T12:11:53.074Z"
    assert normalise_timestamp("2026-11-13T12:11:53Z") == "2026-11-13T12:11:53.000Z"


def test_unexpected_values_are_left_unchanged():
    assert normalise_timestamp("not a time") == "not a time"


def test_internal_fields_are_removed():
    event = to_log_event({"event_id": "e1", "timestamp": "2026-11-13T12:11:53.074000Z",
                          "ingested_at": "2026-11-13T12:11:54.000000Z"})
    assert event == {"event_id": "e1", "timestamp": "2026-11-13T12:11:53.074Z"}

    