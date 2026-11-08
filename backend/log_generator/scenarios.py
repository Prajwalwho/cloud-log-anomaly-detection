"""
Fault scenarios for the log generator.

A Fault changes how one service behaves during a time interval.
A Scenario is a named group of faults (e.g. a cascading failure affects
several services at different times). Times inside a scenario are relative
to the scenario start; build_schedule() places scenarios on the run timeline.

Fault kinds:
  error_burst    calls to the service fail with probability `error_rate`
  latency_spike  call latency is multiplied by `latency_factor`
  new_error      calls fail with a new, never-seen error message (`message`)
  silent         the service stops logging; the gateway gets "connection refused"
"""
from __future__ import annotations

from dataclasses import dataclass, replace

FAULT_KINDS = ("error_burst", "latency_spike", "new_error", "silent")


@dataclass(frozen=True)
class Fault:
    kind: str
    service: str
    start_s: float
    end_s: float
    error_rate: float = 0.0
    latency_factor: float = 1.0
    message: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"Unknown fault kind '{self.kind}'. Allowed: {FAULT_KINDS}")
        if self.end_s <= self.start_s:
            raise ValueError("Fault end_s must be after start_s")
        if not 0.0 <= self.error_rate <= 1.0:
            raise ValueError("error_rate must be between 0 and 1")
        if self.latency_factor < 1.0:
            raise ValueError("latency_factor must be >= 1")
        if self.kind in ("error_burst", "new_error") and self.error_rate == 0:
            raise ValueError(f"{self.kind} fault needs error_rate > 0")
        if self.kind == "latency_spike" and self.latency_factor == 1.0:
            raise ValueError("latency_spike fault needs latency_factor > 1")
        if self.kind == "new_error" and not self.message:
            raise ValueError("new_error fault needs a message")

    def shifted(self, offset_s: float) -> Fault:
        """Return a copy moved later in time by offset_s seconds."""
        return replace(self, start_s=self.start_s + offset_s, end_s=self.end_s + offset_s)

    def is_active(self, t: float) -> bool:
        return self.start_s <= t < self.end_s


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    faults: tuple[Fault, ...]

    @property
    def duration_s(self) -> float:
        return max(fault.end_s for fault in self.faults)


SCENARIOS: dict[str, Scenario] = {
    "error_burst": Scenario(
        name="error_burst",
        description="payment-service fails 40% of calls for 2 minutes",
        faults=(
            Fault("error_burst", "payment-service", 0, 120, error_rate=0.4,
                  description="Database timeouts: 40% of payment calls fail"),
        ),
    ),
    "latency_spike": Scenario(
        name="latency_spike",
        description="order-service becomes 6x slower for 2 minutes",
        faults=(
            Fault("latency_spike", "order-service", 0, 120, latency_factor=6.0,
                  description="Slow database queries: order-service latency x6"),
        ),
    ),
    "new_error": Scenario(
        name="new_error",
        description="inventory-service logs a never-seen error in 15% of calls for 2 minutes",
        faults=(
            Fault("new_error", "inventory-service", 0, 120, error_rate=0.15,
                  message=("Unhandled exception in stock-sync worker {worker_id}: "
                           "java.lang.OutOfMemoryError: Java heap space"),
                  description="Memory exhaustion: new error type in inventory-service"),
        ),
    ),
    "silent_service": Scenario(
        name="silent_service",
        description="auth-service crashes and stops logging for 2 minutes",
        faults=(
            Fault("silent", "auth-service", 0, 120,
                  description="auth-service down: no logs, gateway gets connection refused (503)"),
        ),
    ),
    "cascading_failure": Scenario(
        name="cascading_failure",
        description="shared database degrades: order slows, then payment and inventory fail",
        faults=(
            Fault("latency_spike", "order-service", 0, 180, latency_factor=3.0,
                  description="Shared database slows down: order-service latency x3"),
            Fault("error_burst", "payment-service", 60, 180, error_rate=0.3,
                  description="Payment calls time out as the database degrades"),
            Fault("error_burst", "inventory-service", 90, 180, error_rate=0.2,
                  description="Stock reservations fail as database locks pile up"),
        ),
    ),
}


def build_schedule(
    names: list[str], warmup_s: float = 300.0, gap_s: float = 300.0
) -> tuple[list[tuple[Scenario, float]], float]:
    """
    Place scenarios one after another on the run timeline.

    Timeline: warmup (normal) -> scenario -> gap (normal) -> scenario -> gap ...
    Returns ([(scenario, start_offset_s), ...], total_duration_s).
    """
    schedule: list[tuple[Scenario, float]] = []
    t = warmup_s
    for name in names:
        if name not in SCENARIOS:
            raise ValueError(f"Unknown scenario '{name}'. Available: {list(SCENARIOS)}")
        scenario = SCENARIOS[name]
        schedule.append((scenario, t))
        t += scenario.duration_s + gap_s
    return schedule, t


def schedule_faults(schedule: list[tuple[Scenario, float]]) -> list[Fault]:
    """All faults of a schedule, with absolute times on the run timeline."""
    return [fault.shifted(offset) for scenario, offset in schedule for fault in scenario.faults]