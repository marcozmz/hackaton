"""Monta o AgroContext chamando enrichers. Cada enricher preenche um fato ou registra lacuna.

Nova dimensão (previsão, seguro...) = novo enricher nesta lista.
"""
from __future__ import annotations

import logging
from datetime import date

from flask import current_app

from app.domain.context import AgroContext, VarietyFacts, ZarcFacts, ZoneFacts
from app.domain.zarc import CYCLE_GROUP_NUMBER
from app.errors import UpstreamUnavailable
from app.repositories import catalog_repo, zarc_repo
from app.services.insurance_service import InsuranceService
from app.services.weather_service import WeatherService

log = logging.getLogger(__name__)


def season_for(d: date) -> str:
    """Safra agrícola: julho a junho. 02/10/2026 → '2026/2027'."""
    return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"


class ZarcEnricher:
    name = "zarc"

    def enrich(self, ctx: AgroContext, used: dict) -> None:
        soil_codes = catalog_repo.soil_codes_for_group(ctx.soil.group_code) if ctx.soil else None
        version, rows = zarc_repo.zones(
            ctx.municipality.ibge_code,
            ctx.crop.id,
            soil_codes,
            current_app.config["ZARC_DEFAULT_MANAGEMENT"],
        )
        zones = tuple(ZoneFacts(**r) for r in rows)
        seasons = {z.season_label for z in zones if z.season_label}
        is_current = not seasons or season_for(ctx.as_of) in seasons
        ctx.facts["zarc"] = ZarcFacts(
            version.id if version else None,
            version.version_label if version else None,
            zones,
            is_current,
        )
        if version:
            used["zarc_tabua_risco"] = version


class VarietyEnricher:
    name = "varieties"

    def enrich(self, ctx: AgroContext, used: dict) -> None:
        version, items = catalog_repo.varieties_for(ctx.crop.id, ctx.municipality.uf)
        if version is None:
            ctx.data_gaps.append("cultivars")
            return
        used["zarc_cultivares"] = version
        # Prefere cultivares do(s) grupo(s) de ciclo que o ZARC indica para este município.
        zarc: ZarcFacts | None = ctx.facts.get("zarc")
        groups = {CYCLE_GROUP_NUMBER[z.cycle_code] for z in (zarc.zones if zarc else ()) if z.cycle_code in CYCLE_GROUP_NUMBER}
        if groups:
            matching = [i for i in items if not i["groups"] or set(i["groups"]) & groups or i["groups"] == ["0"]]
            items = matching or items
        ctx.facts["varieties"] = VarietyFacts(version.id, tuple(items), "uf")


class ForecastEnricher:
    name = "forecast"

    def enrich(self, ctx: AgroContext, used: dict) -> None:
        svc = WeatherService()
        if not svc.enabled():
            return  # previsão desligada por config: não é lacuna
        try:
            fc = svc.forecast(ctx.municipality)
        except UpstreamUnavailable:
            ctx.data_gaps.append("forecast")
            return
        ctx.facts["forecast"] = fc
        used["open_meteo"] = fc


class InsuranceEnricher:
    name = "insurance"

    def enrich(self, ctx: AgroContext, used: dict) -> None:
        facts = InsuranceService().facts(ctx.municipality, ctx.crop)
        if facts is None:
            return  # base não carregada: não é lacuna da recomendação
        ctx.facts["insurance"] = facts
        used["sisser"] = facts


ENRICHERS = [ZarcEnricher(), VarietyEnricher(), ForecastEnricher(), InsuranceEnricher()]


class ContextBuilder:
    def __init__(self, enrichers=None):
        self.enrichers = enrichers if enrichers is not None else ENRICHERS

    def build(self, ctx: AgroContext) -> dict:
        """Preenche ctx.facts; devolve {dataset_code: DatasetVersion} usados (para `sources`)."""
        used: dict = {}
        for e in self.enrichers:
            try:
                e.enrich(ctx, used)
            except Exception:  # um enricher falhar não derruba a recomendação
                log.exception("enricher %s falhou", e.name)
                ctx.data_gaps.append(e.name)
        return used
