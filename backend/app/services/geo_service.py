"""Dados do mapa. O backend entrega SIGNIFICADO (nível semântico + texto), nunca cor nem código ZARC.

O frontend só renderiza (Leaflet etc.) e mapeia `level` → cor/ícone.
"""
from __future__ import annotations

from datetime import date

from flask import current_app

from app.domain import decendio as dec
from app.domain.context import ZoneFacts
from app.domain.narrative.narrator import Narrator, SafeDict
from app.domain.engine.engine import risk_from_severity
from app.domain.risk import zarc_risk_severity
from app.domain.zarc import combine
from app.extensions import cache
from app.repositories import catalog_repo, geo_repo, territory_repo, zarc_repo
from app.services.location_service import LocationResult

LEVELS = ("low", "medium", "high", "out_of_window", "no_data")


def _risk_level(risk_pct: int) -> str:
    return risk_from_severity(zarc_risk_severity(risk_pct)).value


class GeoService:
    def __init__(self):
        self.m = Narrator().m["map"]

    def legend(self) -> list[dict]:
        return [{"level": lv, "label": self.m["legend"][lv]} for lv in LEVELS]

    def municipality(self, loc: LocationResult) -> dict:
        mun = loc.municipality
        props = {"ibge_code": mun.ibge_code, "name": mun.name, "uf": mun.uf}
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [mun.lon, mun.lat]},
                "properties": {**props, "kind": "centroid"},
            }
        ]
        geom = geo_repo.geometry(mun.ibge_code, mun.uf)
        if geom:
            features.append({"type": "Feature", "geometry": geom, "properties": {**props, "kind": "boundary"}})
        return {
            "type": "FeatureCollection",
            "features": features,
            "boundary_status": "ok" if geom else "unavailable",
            "source_id": "ibge_malha_municipal",
        }

    def zarc_risk_layer(self, uf: str, crop_slug: str, soil_group: int | None, as_of: date) -> dict:
        uf = uf.upper()
        today = dec.from_date(as_of)
        zv = zarc_repo.current()
        key = f"geo:zarc:{uf}:{crop_slug}:{soil_group}:{today}:{zv.id if zv else 0}"
        if (hit := cache.get(key)) is not None:
            return hit

        crop = catalog_repo.crop_by_slug(crop_slug)
        soil_codes = catalog_repo.soil_codes_for_group(soil_group) if soil_group else None
        version, zones_by_mun = zarc_repo.uf_zones_at(
            uf, crop.id, soil_codes, current_app.config["ZARC_DEFAULT_MANAGEMENT"], today
        )
        geoms = geo_repo.uf_geometries(uf) or {}
        names = {r[0]: r[1] for r in territory_repo.all_light() if r[3] == uf}

        counts = dict.fromkeys(LEVELS, 0)
        features = []
        for ibge, name in names.items():
            zones = zones_by_mun.get(ibge)
            if not zones:
                level = "no_data"
            else:
                cw = combine([ZoneFacts(**z) for z in zones])
                level = _risk_level(cw.windows[today]) if today in cw.windows else "out_of_window"
            counts[level] += 1
            geometry = geoms.get(ibge)
            if geometry is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "ibge_code": ibge,
                        "name": name,
                        "level": level,
                        "label": self.m["feature_label"].format_map(
                            SafeDict(name=name, legend=self.m["legend"][level])
                        ),
                    },
                }
            )
        start, end = dec.bounds(today, as_of.year)
        out = {
            "type": "FeatureCollection",
            "title": self.m["title"].format_map(SafeDict(
                crop=crop.official_name, uf=uf, period=f"{start.day} a {end.day}/{end.month:02d}"
            )),
            "legend": self.legend(),
            "summary": counts,
            "as_of": as_of.isoformat(),
            "soil_group": soil_group,
            "boundary_status": "ok" if geoms else "unavailable",
            "features": features,
            "sources": ["zarc_tabua_risco", "ibge_malha_municipal"],
            "zarc_version": version.version_label if version else None,
        }
        cache.set(key, out, timeout=6 * 3600)
        return out
