"""Caso de uso principal: "para este lugar, cultura e solo, quando plantar?"."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from flask import current_app

from app.domain.context import AgroContext
from app.domain.engine import ENGINE_VERSION, RecommendationEngine
from app.domain.narrative import Narrator
from app.domain.zarc import CYCLE_LABELS, MANAGEMENT_LABELS
from app.extensions import cache
from app.repositories import zarc_repo
from app.services.context_builder import ContextBuilder
from app.services.crop_service import CropService
from app.services.location_service import LocationService
from app.services.source_service import version_ref

SOURCE_NAMES = {
    "zarc_tabua_risco": "ZARC – Tábua de Risco (MAPA)",
    "zarc_cultivares": "ZARC – Cultivares (MAPA)",
}


class RecommendationService:
    def __init__(self):
        self.locations = LocationService()
        self.crops = CropService()
        self.engine = RecommendationEngine()
        self.narrator = Narrator()
        self.builder = ContextBuilder()

    def planting_advice(
        self,
        *,
        municipality: int | None = None,
        place: str | None = None,
        cep: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        crop: str,
        soil: str | int | None = None,
        as_of: date | None = None,
        level: str = "simple",
        debug: bool = False,
    ) -> dict:
        loc = self.locations.resolve(q=place, cep=cep, lat=lat, lon=lon, ibge=municipality)
        crop_ref = self.crops.resolve(crop, loc.municipality.uf)
        soil_ref = self.crops.resolve_soil(soil)
        as_of = as_of or date.today()

        zarc_version = zarc_repo.current()
        key = self._input_hash(loc.municipality.ibge_code, loc.municipality.resolved_by, crop_ref.id,
                               soil_ref.group_code if soil_ref else None, as_of, level,
                               zarc_version.id if zarc_version else None)
        cached = cache.get(key)
        if cached and not debug:
            cached = dict(cached)
            cached["crop"] = {**cached["crop"], "matched_as": crop_ref.matched_as}
            return cached

        ctx = AgroContext(loc.municipality, crop_ref, soil_ref, as_of, level)
        used = self.builder.build(ctx)
        result = self.engine.evaluate(ctx)
        text = self.narrator.narrate(ctx, result)

        out = self._present(ctx, loc, result, text, used, key)
        if debug and current_app.config.get("DEBUG_PAYLOADS"):
            out["debug"] = self._debug(ctx, result)
        else:
            cache.set(key, out, timeout=current_app.config["RECOMMENDATION_CACHE_TTL"])
        return out

    @staticmethod
    def _input_hash(*parts) -> str:
        raw = json.dumps([str(p) for p in parts] + [ENGINE_VERSION])
        return "rec:" + hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _present(self, ctx, loc, result, text, used, key) -> dict:
        w = result.window or {}
        varieties = ctx.facts.get("varieties")
        crop_detail = self.crops.detail(ctx.crop.slug)
        sources = [version_ref(code, SOURCE_NAMES.get(code, code), v) for code, v in used.items()]
        return {
            "id": key.removeprefix("rec:"),
            "location": loc.to_dict(),
            "crop": {
                "slug": ctx.crop.slug,
                "name": ctx.crop.name,
                "matched_as": ctx.crop.matched_as,
                "other_names": crop_detail["other_names"],
            },
            "soil": {"id": ctx.soil.group_code, "name": ctx.soil.name} if ctx.soil else None,
            "status": result.status.value,
            "risk_level": result.risk_level.value,
            "title": text.title,
            "summary": text.summary,
            "reason": text.reason,
            "recommended_window": (
                {
                    "start": w["window_start"],
                    "end": w["window_end"],
                    "label": w["window_label"],
                    "is_current": any(f.code == "zarc_in_window" for f in result.findings),
                    "risk_pct": w.get("risk_pct"),
                }
                if w
                else None
            ),
            "varieties": {
                "status": "ok" if varieties and varieties.items else "unavailable",
                "granularity": varieties.granularity if varieties else None,
                "count": len(varieties.items) if varieties else 0,
                "items": [
                    {"name": i["name"], "holder": i["holder"], "groups": i["groups"]}
                    for i in (varieties.items[:12] if varieties else [])
                ],
                "source_id": "zarc_cultivares",
            },
            "actions": text.actions,
            "explanation": {
                "headline": text.reason,
                "reasons": text.reasons,
            },
            "confidence": {
                "level": result.confidence_level.value,
                "score": result.confidence_score,
                "gaps": text.gaps,
                "assumptions": text.assumptions,
            },
            "validity": {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "as_of": ctx.as_of.isoformat(),
                "valid_until": result.valid_until.isoformat(timespec="seconds"),
            },
            "sources": sources,
            "engine": {"version": result.engine_version, "rules": result.rules},
            # Blocos desejáveis: aparecem quando implementados.
            "forecast": {"status": "unavailable"},
            "insurance": {"status": "unavailable"},
        }

    def _debug(self, ctx, result) -> dict:
        z = ctx.facts.get("zarc")
        return {
            "zones": [
                {
                    "variant": zz.zarc_crop_name,
                    "soil_code": zz.soil_code,
                    "cycle": CYCLE_LABELS.get(zz.cycle_code, zz.cycle_code),
                    "management": MANAGEMENT_LABELS.get(zz.management_code, zz.management_code),
                    "climate_code": zz.climate_code,
                    "portaria": zz.portaria,
                    "windows": dict(sorted(zz.windows.items())),
                }
                for zz in (z.zones if z else ())
            ],
            "findings": [
                {"code": f.code, "severity": f.severity.name, "rule": f.rule_id, "params": f.params, "evidence": f.evidence.data}
                for f in result.findings
            ],
        }
