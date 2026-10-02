"""Consultas ao ZARC. Sempre na versão corrente (is_current) — nunca espalhar esse filtro."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.extensions import db
from app.models import DatasetVersion, SoilType, ZarcWindow, ZarcZone
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
