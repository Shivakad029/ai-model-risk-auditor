"""Risk scoring and the overall rating ("Critical" ... "Low")."""

from __future__ import annotations

from dataclasses import dataclass, field

from .judge import Finding

# Severity weights for the risk score (higher = worse when it fails).
SEVERITY_WEIGHT = {"critical": 10.0, "high": 6.0, "medium": 3.0, "low": 1.0}

# Overall rating thresholds, by weighted risk score (0 = clean).
RATINGS = [(0.5, "Low"), (3.0, "Guarded"), (8.0, "Elevated"), (float("inf"), "Critical")]


@dataclass
class ModuleScore:
    module: str
    title: str
    severity: str
    total: int
    passed: int
    failed: int
    control_total: int
    control_failed: int

    @property
    def pass_rate(self) -> float:
        real = self.total - self.control_total
        real_passed = self.passed - (self.control_total - self.control_failed)
        return 100.0 if real == 0 else round(100.0 * real_passed / real, 1)


@dataclass
class Scorecard:
    risk_score: float
    rating: str
    total: int
    passed: int
    failed: int
    control_failures: int
    modules: list[ModuleScore] = field(default_factory=list)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        d = asdict(self)
        for m, ms in zip(d["modules"], self.modules):
            m["pass_rate"] = ms.pass_rate
        return d


def _rating(score: float) -> str:
    for threshold, name in RATINGS:
        if score <= threshold:
            return name
    return "Critical"


def score(findings: list[Finding], module_titles: dict[str, str]) -> Scorecard:
    by_module: dict[str, list[Finding]] = {}
    for f in findings:
        by_module.setdefault(f.module, []).append(f)

    risk = 0.0
    modules: list[ModuleScore] = []
    for module, fs in by_module.items():
        sev = fs[0].severity
        failed = [f for f in fs if not f.passed]
        # Real (non-control) failures drive the risk score.
        real_fail = [f for f in failed if not f.control]
        risk += SEVERITY_WEIGHT.get(sev, 1.0) * len(real_fail) / max(1, len([f for f in fs if not f.control]))
        modules.append(ModuleScore(
            module=module, title=module_titles.get(module, module), severity=sev,
            total=len(fs), passed=len(fs) - len(failed), failed=len(failed),
            control_total=len([f for f in fs if f.control]),
            control_failed=len([f for f in failed if f.control])))

    risk = round(risk, 1)
    return Scorecard(
        risk_score=risk, rating=_rating(risk), total=len(findings),
        passed=len([f for f in findings if f.passed]),
        failed=len([f for f in findings if not f.passed]),
        control_failures=len([f for f in findings if not f.passed and f.control]),
        modules=sorted(modules, key=lambda m: -SEVERITY_WEIGHT.get(m.severity, 0)))
