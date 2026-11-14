"""
Offset commits that survive a lost group membership.

After a long pause (laptop asleep, process suspended, broker unreachable for longer than the session timeout)
the group coordinator removes the consumer from its group. The next synchronous commit then fails with
"assignment lost" (Day 40: the ingestion service crashed this way after the laptop slept for 9 minutes).

The consumer rejoins by itself on its next poll and continues from the last committed offsets, so the
uncommitted messages are delivered again. That is safe in this project because every consumer is idempotent:
ingestion writes documents with event_id as their id, alerting skips anomalies that already have an alert, and
detection rebuilds its open windows from the replay (service.py). So these errors are reported, not raised.
"""
from __future__ import annotations

import sys

from confluent_kafka import Consumer, KafkaException, TopicPartition

# librdkafka error codes after which the consumer only has to rejoin its group (numeric, so the check does not
# depend on which names the installed confluent-kafka version exposes).
RECOVERABLE = {
    -142: "assignment lost",            # _ASSIGNMENT_LOST
    -168: "nothing to commit",          # _NO_OFFSET
    22: "illegal generation",           # ILLEGAL_GENERATION
    25: "unknown member",               # UNKNOWN_MEMBER_ID
    27: "rebalance in progress",        # REBALANCE_IN_PROGRESS
}


def commit_safely(consumer: Consumer, offsets: list[TopicPartition] | None = None, label: str = "consumer") -> bool:
    """Commit synchronously. Returns False (with a warning) if the group membership was lost; raises otherwise."""
    try:
        if offsets is None:
            consumer.commit(asynchronous=False)
        else:
            consumer.commit(offsets=offsets, asynchronous=False)
        return True
    except KafkaException as exc:
        error = exc.args[0] if exc.args else None
        code = error.code() if hasattr(error, "code") else None
        if code not in RECOVERABLE:
            raise
        if code != -168:
            print(f"  [WARN] {label}: offsets not committed ({RECOVERABLE[code]}). The consumer rejoins its group "
                  f"and the uncommitted messages are delivered again (safe: processing is idempotent).",
                  file=sys.stderr)
        return False