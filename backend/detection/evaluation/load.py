"""
Load test helpers (Phase 10, Day 42). Pure functions, unit-tested; scripts/load_test.py runs the steps.

A load step "keeps up" when every part of the pipeline processes the traffic as fast as it arrives:
- the generator sends the planned traffic in (about) the planned time and Kafka confirms every event;
- ingestion stores logs within KEEP_UP_INGEST_P95_S (p95) and its Kafka lag does not keep growing;
- detection judges each minute within KEEP_UP_DETECT_P95_S (p95) of its end (5 s of that is the grace period).
"""
from __future__ import annotations

import re

KEEP_UP_INGEST_P95_S = 5.0
KEEP_UP_DETECT_P95_S = 10.0
GENERATOR_SLACK = 1.05            # the generator may take 5 % longer than planned
LAG_FLOOR = 1_000                 # lags below this many events never count as growing

_GENERATED = re.compile(r"Generated (\d+) events in ([\d.]+) s")
_KAFKA = re.compile(r"Kafka: (\d+) delivered, (\d+) failed, (\d+) still queued")


def parse_generator_output(text: str) -> dict:
    """Totals the generator prints at the end (stderr). Missing values are None (e.g. it crashed)."""
    result: dict = {"events": None, "elapsed_s": None, "delivered": None, "failed": None, "queued": None}
    if m := _GENERATED.search(text):
        result["events"], result["elapsed_s"] = int(m.group(1)), float(m.group(2))
    if m := _KAFKA.search(text):
        result["delivered"], result["failed"], result["queued"] = (int(g) for g in m.groups())
    return result


def lag_summary(samples: list[int]) -> dict:
    """Ingestion lag samples (events not yet stored) -> max, mean, last, and whether it kept growing.

    Growing: the last third of the step has, on average, more than twice the lag of the first third and over
    LAG_FLOOR events, i.e. the consumer falls further behind instead of catching up after each batch.
    """
    if not samples:
        return {"samples": 0, "max": None, "mean": None, "last": None, "growing": False}
    third = max(1, len(samples) // 3)
    first, last = samples[:third], samples[-third:]
    first_mean, last_mean = sum(first) / len(first), sum(last) / len(last)
    return {
        "samples": len(samples),
        "max": max(samples),
        "mean": round(sum(samples) / len(samples), 1),
        "last": samples[-1],
        "growing": last_mean > LAG_FLOOR and last_mean > 2 * max(first_mean, 1.0),
    }


def lag_stalled(samples: list[int], window: int = 12) -> bool:
    """True if the lag rose at each of the last `window` samples (and is above LAG_FLOOR): nobody is consuming.
    A working consumer stores its backlog batch by batch, so its lag goes down now and then."""
    recent = samples[-window:]
    return (len(recent) == window and recent[-1] > LAG_FLOOR
            and all(later > earlier for earlier, later in zip(recent, recent[1:])))


def step_verdict(planned_s: float, generator: dict, ingest: dict | None, detect: dict | None,
                 lag: dict) -> tuple[bool, list[str]]:
    """(keeps up, reasons why not). ingest / detect are distributions as in latency.distribution (seconds)."""
    reasons = []
    if generator.get("elapsed_s") is None:
        reasons.append("generator did not finish")
    elif generator["elapsed_s"] > planned_s * GENERATOR_SLACK:
        reasons.append(f"generator fell behind ({generator['elapsed_s']:.0f} s for {planned_s:.0f} s of traffic)")
    unconfirmed = (generator.get("failed") or 0) + (generator.get("queued") or 0)
    if unconfirmed:
        reasons.append(f"Kafka did not confirm {unconfirmed} events")
    if ingest is None:
        reasons.append("no logs stored")
    elif ingest["p95"] > KEEP_UP_INGEST_P95_S:
        reasons.append(f"ingestion p95 {ingest['p95']:.1f} s")
    if lag.get("growing"):
        reasons.append(f"ingestion lag kept growing (max {lag['max']:,} events)")
    if detect is None:
        reasons.append("no detection windows stored")
    elif detect["p95"] > KEEP_UP_DETECT_P95_S:
        reasons.append(f"detection p95 {detect['p95']:.1f} s after the minute")
    return not reasons, reasons