"""RecommendationEngine: contexto → achados → resultado agregado. Puro (sem I/O)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone

from app.domain import decendio as dec
from app.domain.context import AgroContext
from app.domain.engine import thresholds as th
from app.domain.engine.finding import Finding
from app.domain.engine.rules.registry import RULES
from app.domain.risk import ConfidenceLevel, RiskLevel, Severity, Status

ENGINE_VERSION = "2026.10.0"

UNFAVORABLE_CODES = {"zarc_out_of_window", "zarc_no_window"}
WINDOW_CODES = ("zarc_in_window", "zarc_out_of_window")


@dataclass
class EngineResult:
    status: Status
    risk_level: RiskLevel
    confidence_score: float
    confidence_level: ConfidenceLevel
    gaps: list[str]
    assumptions: list[str]
    findings: list[Finding]  # ordenados: mais grave/relevante primeiro
    actions: list[str]  # códigos de ação, ordenados e sem repetição
    valid_until: datetime
    window: dict | None = None  # janela recomendada (params do achado de janela)
    engine_version: str = ENGINE_VERSION
    rules: list[dict] = field(default_factory=list)

    @property
    def headline(self) -> Finding | None:
        return self.findings[0] if self.findings else None


def risk_from_severity(sev: Severity) -> RiskLevel:
    if sev <= Severity.INFO:
        return RiskLevel.LOW
    if sev == Severity.ATTENTION:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def _confidence(score: float) -> ConfidenceLevel:
    if score >= th.CONFIDENCE_HIGH:
        return ConfidenceLevel.HIGH
    if score >= th.CONFIDENCE_MEDIUM:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def aggregate(ctx: AgroContext, findings: list[Finding], rules_used: list[dict]) -> EngineResult:
    ordered = sorted(findings, key=lambda f: (-int(f.severity), -f.weight))

    score = 1.0 - sum(f.confidence_penalty for f in findings)
    gaps = sorted({f.gap for f in findings if f.gap} | set(ctx.data_gaps))
    assumptions = sorted({f.assumption for f in findings if f.assumption})

    actions: list[str] = []
    for f in ordered:
        for a in f.actions:
            if a not in actions:
                actions.append(a)

    default_until = datetime.combine(dec.end_of_decendio(ctx.as_of), time(23, 59), tzinfo=timezone.utc)
    valid_until = min([f.evidence.valid_until for f in findings if f.evidence.valid_until] or [default_until])

    window = next((f.params for f in ordered if f.code in WINDOW_CODES), None)

    if any(f.blocks_recommendation for f in findings):
        status, risk = Status.NO_DATA, RiskLevel.UNKNOWN
        ordered = [f for f in ordered if f.blocks_recommendation] + [
            f for f in ordered if not f.blocks_recommendation
        ]
    else:
        worst = max((f.severity for f in findings), default=Severity.OK)
        risk = risk_from_severity(worst)
        if any(f.code in UNFAVORABLE_CODES for f in findings):
            status = Status.UNFAVORABLE
        elif worst >= Severity.ATTENTION:
            status = Status.ATTENTION
        else:
            status = Status.FAVORABLE

    score = max(0.0, min(1.0, round(score, 2)))
    return EngineResult(
        status=status,
        risk_level=risk,
        confidence_score=score,
        confidence_level=_confidence(score),
        gaps=gaps,
        assumptions=assumptions,
        findings=ordered,
        actions=actions,
        valid_until=valid_until,
        window=window,
        rules=rules_used,
    )


class RecommendationEngine:
    def __init__(self, rules=None):
        self.rules = rules if rules is not None else RULES

    def evaluate(self, ctx: AgroContext) -> EngineResult:
        findings: list[Finding] = []
        used: list[dict] = []
        for rule in self.rules:
            if rule.applies(ctx):
                used.append({"id": rule.id, "version": rule.version})
                findings.extend(rule.evaluate(ctx))
        return aggregate(ctx, findings, used)
