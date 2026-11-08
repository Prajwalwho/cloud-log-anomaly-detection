"""
Log generator for the simulated microservice environment.

Produces structured log events in the canonical format defined in
docs/design/contracts.md (Section 2). Traffic is modelled as user requests
("flows") that pass through the API gateway to downstream services, so:
  - related log lines share a trace_id,
  - latencies add up along the call chain,
  - a failure in one service also appears as an error at the gateway.

Usage (run from the project root):
    python -m backend.log_generator.generator --duration 10 --pretty
    python -m backend.log_generator.generator --duration 60 --seed 42
    python -m backend.log_generator.generator --duration 600 --fast --seed 42 --output data/processed/normal_10m.jsonl
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import random
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, TextIO

from .config import settings

SCHEMA_VERSION = "1.0"
LEVELS = ("DEBUG", "INFO", "WARN", "ERROR", "FATAL")

# Probability that a single service call fails under normal conditions
BASE_ERROR_RATE = 0.002
# A call slower than SLOW_FACTOR x its median latency is logged as WARN
SLOW_FACTOR = 3.0
# Spread of the log-normal latency distribution
LATENCY_SIGMA = 0.5
# Probability that a step also writes a DEBUG line (cache hits etc.)
DEBUG_PROBABILITY = 0.3

# Which hosts each service runs on
HOSTS: dict[str, tuple[str, ...]] = {
    "api-gateway": ("node-1", "node-2"),
    "auth-service": ("node-1",),
    "order-service": ("node-2",),
    "payment-service": ("node-2", "node-3"),
    "inventory-service": ("node-3",),
}


# ---------------------------------------------------------------------------
# Traffic model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Step:
    """One downstream service call inside a request flow."""
    service: str
    endpoint: str
    median_ms: float
    ok: str                      # INFO message template on success
    error: str                   # ERROR message template on failure
    error_status: int = 500
    debug: str | None = None     # optional DEBUG message template


@dataclass(frozen=True)
class Flow:
    """A type of user request entering through the API gateway."""
    name: str
    weight: float
    endpoint: str
    success_status: int
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class BackgroundTask:
    """A periodic log line not tied to a user request."""
    service: str
    level: str
    template: str
    interval_s: float


AUTH_VALIDATE = Step(
    service="auth-service",
    endpoint="POST /internal/tokens/validate",
    median_ms=8,
    ok="Token validated for user {user_id}",
    error="Token validation failed for user {user_id}: signing key unavailable",
    debug="Token cache hit for user {user_id}",
)

FLOWS: tuple[Flow, ...] = (
    Flow(
        name="browse_products",
        weight=0.45,
        endpoint="GET /api/products",
        success_status=200,
        steps=(
            Step(
                service="inventory-service",
                endpoint="GET /internal/stock",
                median_ms=15,
                ok="Stock lookup for item {item_id}: {stock} units available",
                error="Stock lookup failed for item {item_id}: database query timeout",
                debug="Cache hit for item {item_id}",
            ),
        ),
    ),
    Flow(
        name="login",
        weight=0.15,
        endpoint="POST /api/login",
        success_status=200,
        steps=(
            Step(
                service="auth-service",
                endpoint="POST /internal/authenticate",
                median_ms=40,
                ok="User {user_id} authenticated successfully",
                error="Authentication error for user {user_id}: user store unavailable",
            ),
        ),
    ),
    Flow(
        name="order_status",
        weight=0.20,
        endpoint="GET /api/orders/{id}",
        success_status=200,
        steps=(
            AUTH_VALIDATE,
            Step(
                service="order-service",
                endpoint="GET /internal/orders",
                median_ms=20,
                ok="Order {order_id} retrieved for user {user_id}",
                error="Failed to load order {order_id}: database connection reset",
            ),
        ),
    ),
    Flow(
        name="checkout",
        weight=0.20,
        endpoint="POST /api/checkout",
        success_status=201,
        steps=(
            AUTH_VALIDATE,
            Step(
                service="order-service",
                endpoint="POST /internal/orders",
                median_ms=30,
                ok="Order {order_id} created for user {user_id} with {qty} items",
                error="Failed to create order for user {user_id}: database write timeout",
            ),
            Step(
                service="inventory-service",
                endpoint="POST /internal/stock/reserve",
                median_ms=20,
                ok="Reserved {qty} units of {item_id} for order {order_id}",
                error="Failed to reserve stock for order {order_id}: inventory lock timeout",
            ),
            Step(
                service="payment-service",
                endpoint="POST /internal/payments",
                median_ms=120,
                ok="Payment {txn_id} processed for order {order_id}: amount {amount} INR",
                error="Payment failed for order {order_id}: card processor timeout after {latency} ms",
                error_status=504,
            ),
        ),
    ),
)

_COMMON_BACKGROUND = (
    ("DEBUG", "Health check passed", 15.0),
    ("INFO", "Connection pool stats: active={active} idle={idle} max=50", 30.0),
)

BACKGROUND_TASKS: tuple[BackgroundTask, ...] = tuple(
    BackgroundTask(service, level, template, interval)
    for service in HOSTS
    for level, template, interval in _COMMON_BACKGROUND
) + (
    BackgroundTask("payment-service", "INFO", "Settlement batch {batch_id} completed: {count} transactions", 60.0),
    BackgroundTask("auth-service", "INFO", "Signing key cache refreshed", 120.0),
    BackgroundTask("inventory-service", "INFO", "Stock sync completed: {count} items updated", 90.0),
)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
def format_timestamp(dt: datetime) -> str:
    """ISO 8601 UTC with millisecond precision, e.g. 2026-11-08T10:15:30.123Z."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class LogGenerator:
    """
    Generates log events in timestamp order.

    Request arrivals follow a Poisson process whose rate varies smoothly over
    time (a sine wave), so "normal" traffic has natural peaks and dips.
    """

    def __init__(
        self,
        rate: float,
        seed: int | None = None,
        start: datetime | None = None,
        diurnal_period_s: float = 600.0,
        diurnal_amplitude: float = 0.3,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if not 0 <= diurnal_amplitude < 1:
            raise ValueError("diurnal_amplitude must be in [0, 1)")

        self.rate = rate
        self.rng = random.Random(seed)
        self.start = start or datetime.now(timezone.utc)
        self.diurnal_period_s = diurnal_period_s
        self.diurnal_amplitude = diurnal_amplitude

        self._heap: list[tuple[float, int, dict]] = []   # (offset_seconds, sequence, event)
        self._seq = 0
        self._flow_weights = [flow.weight for flow in FLOWS]
        # Stagger background tasks so they don't all fire at t = 0
        self._background_next = [self.rng.uniform(0, task.interval_s) for task in BACKGROUND_TASKS]

    # ---------------- public API ----------------
    def events(self, duration_s: float) -> Iterator[tuple[float, dict]]:
        """Yield (offset_seconds, event) pairs in timestamp order for duration_s seconds."""
        t = 0.0
        while True:
            t += self.rng.expovariate(self.rate * self._rate_multiplier(t))
            if t > duration_s:
                break
            self._schedule_background(t)
            self._schedule_flow(t)
            while self._heap and self._heap[0][0] <= t:
                offset, _, event = heapq.heappop(self._heap)
                yield offset, event

        # Emit remaining events that fall inside the duration
        self._schedule_background(duration_s)
        while self._heap and self._heap[0][0] <= duration_s:
            offset, _, event = heapq.heappop(self._heap)
            yield offset, event

    # ---------------- traffic ----------------
    def _rate_multiplier(self, t: float) -> float:
        return 1.0 + self.diurnal_amplitude * math.sin(2 * math.pi * t / self.diurnal_period_s)

    def _schedule_flow(self, t0: float) -> None:
        """Simulate one user request starting at offset t0 and queue its log events."""
        flow = self.rng.choices(FLOWS, weights=self._flow_weights)[0]
        ctx = self._context()
        trace_id = f"{self.rng.getrandbits(64):016x}"

        elapsed_ms = self.rng.uniform(1.0, 3.0)   # gateway routing overhead
        failed: Step | None = None

        for step in flow.steps:
            latency = self._latency(step.median_ms)
            ctx["latency"] = round(latency)
            done_at = t0 + (elapsed_ms + latency) / 1000
            host = self.rng.choice(HOSTS[step.service])

            if self.rng.random() < BASE_ERROR_RATE:
                self._push(done_at, self._event(
                    done_at, step.service, "ERROR", step.error.format(**ctx),
                    host=host, trace_id=trace_id, endpoint=step.endpoint,
                    status_code=step.error_status, latency_ms=latency,
                ))
                elapsed_ms += latency
                failed = step
                break   # the gateway stops the request at the first failure

            if step.debug and self.rng.random() < DEBUG_PROBABILITY:
                debug_at = t0 + elapsed_ms / 1000 + 0.0005
                self._push(debug_at, self._event(
                    debug_at, step.service, "DEBUG", step.debug.format(**ctx),
                    host=host, trace_id=trace_id, endpoint=step.endpoint,
                ))

            threshold = SLOW_FACTOR * step.median_ms
            if latency > threshold:
                level = "WARN"
                message = (f"Slow response on {step.endpoint}: {round(latency)} ms "
                           f"exceeds threshold of {round(threshold)} ms")
            else:
                level = "INFO"
                message = step.ok.format(**ctx)

            self._push(done_at, self._event(
                done_at, step.service, level, message,
                host=host, trace_id=trace_id, endpoint=step.endpoint,
                status_code=200, latency_ms=latency,
            ))
            elapsed_ms += latency

        # The gateway logs last, with the total request latency
        gateway_ms = elapsed_ms + self.rng.uniform(1.0, 3.0)
        done_at = t0 + gateway_ms / 1000
        if failed:
            level, status = "ERROR", 502
            message = (f"{flow.endpoint} failed with status 502 in {round(gateway_ms)} ms: "
                       f"{failed.service} returned an error")
        else:
            level, status = "INFO", flow.success_status
            message = f"{flow.endpoint} completed with status {status} in {round(gateway_ms)} ms"

        self._push(done_at, self._event(
            done_at, "api-gateway", level, message,
            trace_id=trace_id, endpoint=flow.endpoint,
            status_code=status, latency_ms=gateway_ms,
        ))

    def _schedule_background(self, until: float) -> None:
        """Queue all periodic background log lines due up to offset `until`."""
        for i, task in enumerate(BACKGROUND_TASKS):
            while self._background_next[i] <= until:
                due = self._background_next[i]
                self._push(due, self._event(due, task.service, task.level, task.template.format(**self._context())))
                self._background_next[i] = due + task.interval_s * self.rng.uniform(0.9, 1.1)

    # ---------------- helpers ----------------
    def _latency(self, median_ms: float) -> float:
        return max(1.0, self.rng.lognormvariate(math.log(median_ms), LATENCY_SIGMA))

    def _context(self) -> dict:
        """Random values for the variable parts of log messages."""
        rng = self.rng
        return {
            "user_id": f"u{rng.randint(1000, 9999)}",
            "order_id": rng.randint(100000, 999999),
            "item_id": f"SKU-{rng.randint(100, 999)}",
            "qty": rng.randint(1, 5),
            "stock": rng.randint(0, 500),
            "amount": f"{rng.uniform(99, 4999):.2f}",
            "txn_id": f"txn_{rng.getrandbits(40):010x}",
            "active": rng.randint(2, 20),
            "idle": rng.randint(5, 30),
            "batch_id": rng.randint(1000, 9999),
            "count": rng.randint(50, 500),
            "latency": 0,
        }

    def _push(self, offset: float, event: dict) -> None:
        heapq.heappush(self._heap, (offset, self._seq, event))
        self._seq += 1

    def _event(
        self,
        offset: float,
        service: str,
        level: str,
        message: str,
        *,
        host: str | None = None,
        trace_id: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        latency_ms: float | None = None,
    ) -> dict:
        """Build one event in the canonical log schema (contracts.md, Section 2)."""
        return {
            "schema_version": SCHEMA_VERSION,
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "timestamp": format_timestamp(self.start + timedelta(seconds=offset)),
            "service": service,
            "host": host or self.rng.choice(HOSTS[service]),
            "level": level,
            "message": message,
            "trace_id": trace_id,
            "endpoint": endpoint,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
            "metadata": {},
        }


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate simulated microservice logs.")
    parser.add_argument("--rate", type=float, default=settings.generator_rate,
                        help="average user requests per second (default: %(default)s)")
    parser.add_argument("--duration", type=float, default=10.0,
                        help="seconds of logs to generate; 0 = run until Ctrl+C (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=settings.generator_seed,
                        help="random seed for reproducible output")
    parser.add_argument("--fast", action="store_true",
                        help="generate as fast as possible instead of in real time")
    parser.add_argument("--output", type=Path,
                        help="write JSON lines to this file instead of the console")
    parser.add_argument("--pretty", action="store_true",
                        help="human-readable console output instead of JSON")
    return parser.parse_args(argv)


def format_pretty(event: dict) -> str:
    return (f"{event['timestamp']}  {event['level']:<5}  {event['service']:<17}  "
            f"{event['host']:<6}  {event['message']}")


def print_summary(levels: Counter, services: Counter, elapsed_s: float) -> None:
    total = sum(levels.values())
    out = sys.stderr
    print(f"\nGenerated {total} events in {elapsed_s:.1f} s", file=out)
    if total == 0:
        return
    print("By level:", file=out)
    for level in LEVELS:
        if levels[level]:
            print(f"  {level:<6} {levels[level]:>8}  ({100 * levels[level] / total:5.2f}%)", file=out)
    print("By service:", file=out)
    for service in HOSTS:
        print(f"  {service:<18} {services[service]:>8}", file=out)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    duration = math.inf if args.duration <= 0 else args.duration
    generator = LogGenerator(rate=args.rate, seed=args.seed)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        out: TextIO = args.output.open("w", encoding="utf-8", newline="\n")
    else:
        out = sys.stdout

    levels: Counter = Counter()
    services: Counter = Counter()
    wall_start = time.monotonic()

    try:
        for offset, event in generator.events(duration):
            if not args.fast:
                delay = wall_start + offset - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            line = format_pretty(event) if (args.pretty and not args.output) else json.dumps(event)
            out.write(line + "\n")
            levels[event["level"]] += 1
            services[event["service"]] += 1
    except KeyboardInterrupt:
        pass
    finally:
        if args.output:
            out.close()
        else:
            out.flush()

    print_summary(levels, services, time.monotonic() - wall_start)
    return 0


if __name__ == "__main__":
    sys.exit(main())