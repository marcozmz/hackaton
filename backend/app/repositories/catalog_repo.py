from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Crop, CropAlias, CropVariety, Dataset, DatasetVersion, SoilType, VarietyZone


def crop_by_slug(slug: str) -> Crop | None:
    return db.session.scalar(select(Crop).where(Crop.slug == slug, Crop.is_active.is_(True)))


def crop_by_id(crop_id: int) -> Crop | None:
    return db.session.get(Crop, crop_id)


def list_crops() -> list[Crop]:
    return list(db.session.scalars(select(Crop).where(Crop.is_active.is_(True)).order_by(Crop.official_name)))


def aliases_exact(normalized: str, uf: str | None = None) -> list[CropAlias]:
    q = select(CropAlias).where(CropAlias.alias_normalized == normalized, CropAlias.status == "approved")
    rows = list(db.session.scalars(q))
    return [a for a in rows if a.region_scope_uf in (None, uf)]


def all_aliases() -> list[tuple[int, str, str | None]]:
    """(crop_id, alias_normalized, region_scope_uf) aprovados — base da busca aproximada."""
    q = select(CropAlias.crop_id, CropAlias.alias_normalized, CropAlias.region_scope_uf).where(
        CropAlias.status == "approved"
    )
    return [tuple(r) for r in db.session.execute(q)]


def aliases_of(crop_id: int) -> list[CropAlias]:
    q = select(CropAlias).where(CropAlias.crop_id == crop_id, CropAlias.status == "approved")
    return list(db.session.scalars(q.order_by(CropAlias.kind, CropAlias.alias)))


def soils() -> list[SoilType]:
    return list(db.session.scalars(select(SoilType).order_by(SoilType.zarc_code)))


def soil_codes_for_group(group_code: int) -> list[int]:
    return list(db.session.scalars(select(SoilType.zarc_code).where(SoilType.group_code == group_code)))


def current_version(dataset_code: str) -> DatasetVersion | None:
    return db.session.scalar(
        select(DatasetVersion)
        .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
        .where(Dataset.code == dataset_code, DatasetVersion.is_current.is_(True))
    )


def varieties_for(crop_id: int, uf: str) -> tuple[DatasetVersion | None, list[dict]]:
    version = current_version("zarc_cultivares")
    if version is None:
        return None, []
    q = (
        select(CropVariety.name, CropVariety.holder, VarietyZone.group_code, VarietyZone.zarc_crop_name)
        .join(VarietyZone, VarietyZone.variety_id == CropVariety.id)
        .where(
            VarietyZone.dataset_version_id == version.id,
            VarietyZone.uf == uf,
            CropVariety.crop_id == crop_id,
        )
        .order_by(CropVariety.name)
    )
    items: dict[str, dict] = {}
    for name, holder, group, zname in db.session.execute(q):
        it = items.setdefault(name, {"name": name, "holder": holder, "groups": set(), "zarc_crop_names": set()})
        if group:
            it["groups"].add(group)
        it["zarc_crop_names"].add(zname)
    out = []
    for it in items.values():
        out.append({**it, "groups": sorted(it["groups"]), "zarc_crop_names": sorted(it["zarc_crop_names"])})
    return version, out
