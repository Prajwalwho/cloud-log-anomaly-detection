"""
Severity grading (detection-design.md, Section 5).

The model decides WHETHER a window is anomalous; these rules grade HOW SEVERE it is, from what the window
shows compared with the service's normal behaviour (baselines learned from training windows). Every grade
carries human-readable reasons.

    Signal                    MEDIUM     HIGH       CRITICAL
    error rate                >= 1%      >= 5%      >= 20%
    log volume vs normal                 <= 50%     <= 10%, or no logs at all
    p95 latency vs normal     >= 1.5x    >= 3x
    new message types         any

Severity = the highest signal found; LOW if the model flagged the window but no signal crosses a limit.
The limits are design choices based on operational reasoning (not fitted to labels); they were checked
against the fault and fault-free runs (Day 25).

Ratios are shown with two decimals: with one decimal, 2.97x appeared as "3.0x" on a MEDIUM anomaly and seemed
to contradict the 3x HIGH limit (Day 25).
"""
from __future__ import annotations

from dataclasses import dataclass

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ERROR_RATE_LIMITS = ((0.20, "CRITICAL"), (0.05, "HIGH"), (0.01, "MEDIUM"))
VOLUME_SHARE_LIMITS = ((0.10, "CRITICAL"), (0.50, "HIGH"))      # log count <= share of normal
LATENCY_RATIO_LIMITS = ((3.0, "HIGH"), (1.5, "MEDIUM"))         # p95 >= ratio x normal


@dataclass(frozen=True)
class Grade:
    severity: str
    reasons: tuple[str, ...]


def grade(summary: dict, baseline: dict | None = None, no_logs: bool = False) -> Grade:
    findings: list[tuple[str, str]] = []
    count = summary["log_count"]
    normal_count = baseline.get("log_count") if baseline else None

    if no_logs:
        text = f"no logs (normally ~{normal_count:.0f} per minute)" if normal_count else "no logs"
        findings.append(("CRITICAL", text))
    elif count:
        error_rate = summary["error_count"] / count
        for limit, severity in ERROR_RATE_LIMITS:
            if error_rate >= limit:
                findings.append((severity, f"error rate {error_rate:.1%}"))
                break
        if normal_count:
            share = count / normal_count
            for limit, severity in VOLUME_SHARE_LIMITS:
                if share <= limit:
                    findings.append((severity, f"log volume {share:.0%} of normal ({count} vs ~{normal_count:.0f})"))
                    break
        p95, normal_p95 = summary.get("p95_latency_ms"), baseline.get("p95_latency_ms") if baseline else None
        if p95 and normal_p95:
            ratio = p95 / normal_p95
            for limit, severity in LATENCY_RATIO_LIMITS:
                if ratio >= limit:
                    findings.append((severity, f"p95 latency {p95:.0f} ms ({ratio:.2f}x normal)"))
                    break
        if summary.get("new_templates"):
            findings.append(("MEDIUM", f"{summary['new_templates']} new message type(s)"))

    if not findings:
        return Grade("LOW", ("unusual log pattern (no single signal above its limit)",))
    findings.sort(key=lambda f: SEVERITIES.index(f[0]), reverse=True)
    return Grade(findings[0][0], tuple(reason for _, reason in findings))