from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.risk import Severity


@dataclass(frozen=True)
class Evidence:
    source_id: str | None  # código do dataset (zarc_tabua_risco, zarc_cultivares...) ou "engine"
    dataset_version_id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    valid_until: datetime | None = None


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    weight: float
    evidence: Evidence
    rule_id: str
    rule_version: str
    params: dict[str, Any] = field(default_factory=dict)
    actions: tuple[str, ...] = ()
    confidence_penalty: float = 0.0
    gap: str | None = None  # código de lacuna p/ confidence.gaps
    assumption: str | None = None  # código de suposição p/ confidence.assumptions
    blocks_recommendation: bool = False  # ex.: sem zoneamento
