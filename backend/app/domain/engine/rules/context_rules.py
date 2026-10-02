"""Regras sobre a qualidade do contexto: solo, localização, cultivares."""
from __future__ import annotations

from app.domain.context import AgroContext, VarietyFacts
from app.domain.engine import thresholds as th
from app.domain.engine.finding import Evidence, Finding
from app.domain.risk import Severity

APPROXIMATE_LOCATION = {"fuzzy_name", "nearest_centroid"}


class SoilUnspecifiedRule:
    id, version = "soil_unspecified", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        return "zarc" in ctx.facts and bool(ctx.facts["zarc"].zones)

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        if ctx.soil is None:
            return [
                Finding(
                    "soil_unspecified", Severity.INFO, 0.6, Evidence("engine"),
                    self.id, self.version,
                    actions=("inform_soil",),
                    confidence_penalty=th.CONFIDENCE_PENALTY["soil_unspecified"],
                    assumption="soil_unspecified",
                )
            ]
        codes = {z.soil_code for z in ctx.facts["zarc"].zones}
        if any(c >= 11 for c in codes):
            return [
                Finding(
                    "soil_ad_approximation", Severity.INFO, 0.2,
                    Evidence("engine", data={"soil_codes": sorted(codes)}),
                    self.id, self.version,
                    params={"soil": ctx.soil.name},
                    confidence_penalty=th.CONFIDENCE_PENALTY["soil_ad_approximation"],
                    assumption="soil_ad_approximation",
                )
            ]
        return []


class LocationApproximateRule:
    id, version = "location_approximate", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        return ctx.municipality.resolved_by in APPROXIMATE_LOCATION

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        return [
            Finding(
                "location_approximate", Severity.INFO, 0.3,
                Evidence("engine", data={"resolved_by": ctx.municipality.resolved_by}),
                self.id, self.version,
                params={"municipality": ctx.municipality.name, "uf": ctx.municipality.uf},
                actions=("confirm_location",),
                confidence_penalty=th.CONFIDENCE_PENALTY["location_approximate"],
                assumption="location_approximate",
            )
        ]


class CultivarHintRule:
    id, version = "cultivar_hint", "1.0"
    SOURCE = "zarc_cultivares"

    def applies(self, ctx: AgroContext) -> bool:
        z = ctx.facts.get("zarc")
        return "varieties" in ctx.facts and bool(z and z.zones)

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        v: VarietyFacts = ctx.facts["varieties"]
        ev = Evidence(self.SOURCE, v.dataset_version_id, {"count": len(v.items), "granularity": v.granularity})
        if not v.items:
            return [
                Finding(
                    "cultivar_unknown", Severity.INFO, 0.3, ev, self.id, self.version,
                    params={"crop": ctx.crop.name, "uf": ctx.municipality.uf},
                    actions=("ask_cultivar_technician",),
                    confidence_penalty=th.CONFIDENCE_PENALTY["cultivar_unknown"],
                    gap="cultivars",
                )
            ]
        names = [i["name"] for i in v.items[: th.MAX_VARIETIES_SHOWN]]
        return [
            Finding(
                "cultivar_available", Severity.OK, 0.6, ev, self.id, self.version,
                params={
                    "count": len(v.items),
                    "examples": ", ".join(names[:3]),
                    "uf": ctx.municipality.uf,
                    "crop": ctx.crop.name,
                },
                actions=("choose_cultivar",),
                confidence_penalty=th.CONFIDENCE_PENALTY["cultivar_by_uf"] if v.granularity == "uf" else 0.0,
                assumption="cultivar_by_uf" if v.granularity == "uf" else None,
            )
        ]
