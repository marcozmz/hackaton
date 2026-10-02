"""Consultas ao ZARC. Sempre na versão corrente (is_current) — nunca espalhar esse filtro."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.extensions import db
from app.models import DatasetVersion, Municipality, SoilType, ZarcWindow, ZarcZone
from app.repositories.catalog_repo import current_version

DATASET = "zarc_tabua_risco"


def current() -> DatasetVersion | None:
    return current_version(DATASET)


def zones(
    municipality_ibge: int,
    crop_id: int,
    soil_codes: list[int] | None,
    management_code: int,
) -> tuple[DatasetVersion | None, list[dict]]:
    """Zonas + janelas. `soil_codes=None` → todos os solos.

    Se não houver zona no manejo pedido (ex.: sequeiro), devolve o que existir
    em outro manejo — o chamador decide como comunicar.
    """
    version = current()
    if version is None:
        return None, []
    q = (
        select(ZarcZone, SoilType.zarc_code, SoilType.group_code)
        .join(SoilType, SoilType.id == ZarcZone.soil_type_id)
        .where(
            ZarcZone.dataset_version_id == version.id,
            ZarcZone.municipality_ibge == municipality_ibge,
            ZarcZone.crop_id == crop_id,
        )
    )
    if soil_codes:
        q = q.where(SoilType.zarc_code.in_(soil_codes))
    rows = list(db.session.execute(q))
    preferred = [r for r in rows if r[0].management_code == management_code]
    rows = preferred or rows
    if not rows:
        return version, []

    ids = [r[0].id for r in rows]
    windows: dict[int, dict[int, int]] = defaultdict(dict)
    for i in range(0, len(ids), 500):
        wq = select(ZarcWindow.zone_id, ZarcWindow.decendio, ZarcWindow.risk_pct).where(
            ZarcWindow.zone_id.in_(ids[i : i + 500])
        )
        for zid, d, r in db.session.execute(wq):
            windows[zid][d] = r

    out = []
    for z, soil_code, soil_group in rows:
        out.append(
            {
                "zarc_crop_name": z.zarc_crop_name,
                "soil_code": soil_code,
                "soil_group": soil_group,
                "cycle_code": z.cycle_code,
                "management_code": z.management_code,
                "climate_code": z.climate_code,
                "management_level": z.management_level,
                "portaria": z.portaria,
                "season_label": z.season_label,
                "windows": windows.get(z.id, {}),
            }
        )
    return version, out


def has_crop_anywhere(crop_id: int) -> bool:
    version = current()
    if version is None:
        return False
    q = select(ZarcZone.id).where(ZarcZone.dataset_version_id == version.id, ZarcZone.crop_id == crop_id).limit(1)
    return db.session.scalar(q) is not None


def uf_zones_at(uf: str, crop_id: int, soil_codes: list[int] | None, management_code: int, decendio: int):
    """Para a camada de mapa: zonas da cultura na UF + risco só no decêndio pedido.

    Devolve (version, {ibge: [zona_dict...]}) onde windows = {decendio: risco} ou {}.
    Duas consultas para a UF inteira (sem N+1).
    """
    version = current()
    if version is None:
        return None, {}
    zq = (
        select(ZarcZone, SoilType.zarc_code, SoilType.group_code)
        .join(SoilType, SoilType.id == ZarcZone.soil_type_id)
        .join(Municipality, Municipality.ibge_code == ZarcZone.municipality_ibge)
        .where(
            ZarcZone.dataset_version_id == version.id,
            ZarcZone.crop_id == crop_id,
            Municipality.uf == uf,
        )
    )
    if soil_codes:
        zq = zq.where(SoilType.zarc_code.in_(soil_codes))
    rows = list(db.session.execute(zq))
    by_mun: dict[int, list] = defaultdict(list)
    for r in rows:
        by_mun[r[0].municipality_ibge].append(r)
    # mesmo critério da recomendação: prefere o manejo pedido (sequeiro), senão o que houver
    for ibge, rs in by_mun.items():
        preferred = [r for r in rs if r[0].management_code == management_code]
        by_mun[ibge] = preferred or rs

    ids = [r[0].id for rs in by_mun.values() for r in rs]
    risk: dict[int, int] = {}
    for i in range(0, len(ids), 900):
        wq = select(ZarcWindow.zone_id, ZarcWindow.risk_pct).where(
            ZarcWindow.zone_id.in_(ids[i : i + 900]), ZarcWindow.decendio == decendio
        )
        risk.update(dict(db.session.execute(wq).all()))

    out: dict[int, list[dict]] = {}
    for ibge, rs in by_mun.items():
        out[ibge] = [
            {
                "zarc_crop_name": z.zarc_crop_name,
                "soil_code": soil_code,
                "soil_group": soil_group,
                "cycle_code": z.cycle_code,
                "management_code": z.management_code,
                "climate_code": z.climate_code,
                "management_level": z.management_level,
                "portaria": z.portaria,
                "season_label": z.season_label,
                "windows": {decendio: risk[z.id]} if z.id in risk else {},
            }
            for z, soil_code, soil_group in rs
        ]
    return version, out
