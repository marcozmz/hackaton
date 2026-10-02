"""Enums semânticos. O frontend recebe só estes valores e decide cor/ícone."""
from __future__ import annotations

from enum import Enum, IntEnum


class Severity(IntEnum):  # a ordem importa: risco = pior achado
    OK = 0
    INFO = 1
    ATTENTION = 2
    HIGH = 3
    BLOCKING = 4


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class Status(str, Enum):
    FAVORABLE = "favorable"
    ATTENTION = "attention"
    UNFAVORABLE = "unfavorable"
    NO_DATA = "no_data"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


LanguageLevel = str  # "simple" | "standard" | "technical"
LANGUAGE_LEVELS = ("simple", "standard", "technical")


def zarc_risk_severity(risk_pct: int) -> Severity:
    """Risco ZARC (probabilidade de perda) → severidade.

    20% baixo · 30% médio · 40% alto (ainda dentro do zoneamento, mas o pior aceito).
    """
    if risk_pct <= 20:
        return Severity.OK
    if risk_pct <= 30:
        return Severity.ATTENTION
    return Severity.HIGH
