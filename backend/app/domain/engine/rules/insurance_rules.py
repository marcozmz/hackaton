"""Seguro rural: informativo, nunca altera o risco."""
from __future__ import annotations

from app.domain.context import AgroContext, InsuranceFacts
from app.domain.engine.finding import Evidence, Finding
from app.domain.risk import Severity

SOURCE = "sisser"


class InsuranceHintRule:
    id, version = "insurance_hint", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        z = ctx.facts.get("zarc")
        return ctx.facts.get("insurance") is not None and bool(z and z.zones)

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        ins: InsuranceFacts = ctx.facts["insurance"]
        ev = Evidence(SOURCE, ins.dataset_version_id, {"year": ins.year, "scope": ins.scope})
        if ins.stat is None:
            return [
                Finding("insurance_available", Severity.INFO, 0.2, ev, self.id, self.version,
                        params={"year": ins.year}, actions=("consider_insurance",))
            ]
        s = ins.stat
        code = "insurance_uptake" if ins.about_crop else "insurance_uptake_any_crop"
        return [
            Finding(
                code, Severity.INFO, 0.25, ev, self.id, self.version,
                params={
                    "year": ins.year,
                    "policies": s["policies_count"],
                    "area_ha": f"{round(s['insured_area_ha']):,}".replace(",", "."),
                    "where": ctx.municipality.name if ins.scope == "municipality" else ctx.municipality.uf,
                    "subsidy_pct": round(s["subsidy_share_pct"] or 0),
                    "premium_pct": s["avg_premium_rate_pct"],
                },
                actions=("consider_insurance",),
            )
        ]
