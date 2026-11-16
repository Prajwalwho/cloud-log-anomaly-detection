"""Load test helpers (Day 42): generator output, ingestion lag trend, keep-up verdict."""
from backend.detection.evaluation.load import lag_stalled, lag_summary, parse_generator_output, step_verdict

OUTPUT = """  ... 85830 events sent, 85827 confirmed by Kafka

Kafka: 98179 delivered, 0 failed, 0 still queued

Generated 98179 events in 300.4 s
By level:
"""
OK_GEN = {"events": 98179, "elapsed_s": 300.4, "delivered": 98179, "failed": 0, "queued": 0}
FAST = {"p50": 0.6, "p95": 1.1, "max": 1.6}
JUDGED = {"p50": 5.9, "p95": 6.4, "max": 6.5}
STEADY = {"max": 400, "growing": False}


def test_parse_generator_output():
    assert parse_generator_output(OUTPUT) == OK_GEN


def test_parse_generator_output_missing_totals():
    assert parse_generator_output("Traceback ...") == {
        "events": None, "elapsed_s": None, "delivered": None, "failed": None, "queued": None}


def test_lag_that_stays_low_is_not_growing():
    summary = lag_summary([300, 50, 400, 120, 380, 90])
    assert summary["max"] == 400 and summary["last"] == 90 and summary["growing"] is False


def test_lag_that_builds_up_is_growing():
    assert lag_summary([200, 900, 3_000, 8_000, 15_000, 24_000])["growing"] is True


def test_small_lag_never_counts_as_growing():
    assert lag_summary([10, 20, 400, 600, 800, 900])["growing"] is False   # below LAG_FLOOR


def test_empty_lag():
    assert lag_summary([]) == {"samples": 0, "max": None, "mean": None, "last": None, "growing": False}


def test_step_keeps_up():
    assert step_verdict(300, OK_GEN, FAST, JUDGED, STEADY) == (True, [])


def test_step_reasons():
    slow_gen = {**OK_GEN, "elapsed_s": 340.0, "failed": 3}
    keeps_up, reasons = step_verdict(300, slow_gen, {"p50": 4, "p95": 9.5, "max": 20}, {"p50": 9, "p95": 14.0},
                                     {"max": 50_000, "growing": True})
    assert keeps_up is False
    assert reasons == [
        "generator fell behind (340 s for 300 s of traffic)",
        "Kafka did not confirm 3 events",
        "ingestion p95 9.5 s",
        "ingestion lag kept growing (max 50,000 events)",
        "detection p95 14.0 s after the minute",
    ]


def test_step_without_data():
    keeps_up, reasons = step_verdict(300, {"elapsed_s": None}, None, None, {"growing": False})
    assert keeps_up is False
    assert reasons == ["generator did not finish", "no logs stored", "no detection windows stored"]


def test_lag_stalled_when_nobody_consumes():
    assert lag_stalled([1_000 + 370 * i for i in range(20)]) is True        # Day 42: ingestion was not running


def test_lag_not_stalled_when_consumer_works():
    working = [400, 900, 200, 1_500, 600, 2_000, 300, 1_800, 900, 2_500, 700, 3_000, 1_100, 2_800]
    assert lag_stalled(working) is False
    assert lag_stalled([100, 200, 300]) is False                             # too few samples
    assert lag_stalled(list(range(10, 130, 10))) is False                    # rising, but below LAG_FLOOR