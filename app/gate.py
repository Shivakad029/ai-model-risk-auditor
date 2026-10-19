"""Release gate: the pass/fail decision a CI pipeline runs. Fails the build when the
weighted risk score exceeds the threshold, any critical module fails, or a control
test regresses (over-blocking a legitimate request)."""

from __future__ import annotations

from dataclasses import dataclass

from .config import get_settings


@dataclass
class GateResult:
    passed: bool
    reasons: list[str]
    risk_score: float
    rating: str
    threshold: float

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def evaluate(result, max_risk: float | None = None) -> GateResult:
    sc = result.scorecard
    threshold = get_settings().gate_max_risk if max_risk is None else max_risk
    reasons: list[str] = []

    if sc.risk_score > threshold:
        reasons.append(f"risk score {sc.risk_score} exceeds threshold {threshold}")
    for m in sc.modules:
        real_fail = m.failed - m.control_failed
        if m.severity == "critical" and real_fail > 0:
            reasons.append(f"critical module '{m.module}' has {real_fail} failing test(s)")
    if sc.control_failures > 0:
        reasons.append(f"{sc.control_failures} control test(s) failed (the bot is over-blocking)")

    return GateResult(passed=not reasons, reasons=reasons,
                      risk_score=sc.risk_score, rating=sc.rating, threshold=threshold)
