"""Regras ativas. Regra nova = nova classe + uma linha aqui + mensagens no YAML."""
from app.domain.engine.rules.context_rules import (
    CultivarHintRule,
    LocationApproximateRule,
    SoilUnspecifiedRule,
)
from app.domain.engine.rules.zarc_rules import ZarcCoverageRule, ZarcWindowRule

RULES = [
    ZarcCoverageRule(),
    ZarcWindowRule(),
    SoilUnspecifiedRule(),
    CultivarHintRule(),
    LocationApproximateRule(),
    # desejável: ForecastHeavyRainRule(), ForecastDrySpellRule(), InsuranceHintRule()
]
