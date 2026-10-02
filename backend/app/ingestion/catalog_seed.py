"""Seeds versionados em app/seeds/*.yaml: fontes, solos, culturas e aliases."""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import select

from app.domain.text import normalize_name
from app.extensions import db
from app.models import Crop, CropAlias, DataSource, Dataset, SoilType

SEEDS = Path(__file__).resolve().parent.parent / "seeds"


def _load(name: str) -> dict:
    with open(SEEDS / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_crops_yaml() -> list[dict]:
    return _load("crops.yaml")["crops"]


def load_soil_groups() -> list[dict]:
    return _load("soils.yaml")["groups"]


def seed_sources() -> int:
    data = _load("sources.yaml")
    by_code = {s.code: s for s in db.session.scalars(select(DataSource))}
    for s in data["sources"]:
        obj = by_code.get(s["code"]) or DataSource(code=s["code"])
        for k, v in s.items():
            setattr(obj, k, v)
        db.session.add(obj)
        by_code[s["code"]] = obj
    db.session.flush()
    existing = {d.code: d for d in db.session.scalars(select(Dataset))}
    for d in data["datasets"]:
        obj = existing.get(d["code"]) or Dataset(code=d["code"])
        for k, v in d.items():
            if k == "source":
                obj.source_id = by_code[v].id
            else:
                setattr(obj, k, v)
        db.session.add(obj)
    db.session.commit()
    return len(data["datasets"])


def seed_soils() -> int:
    data = _load("soils.yaml")
    groups = {g["code"]: g for g in data["groups"]}
    existing = {s.zarc_code: s for s in db.session.scalars(select(SoilType))}
    for s in data["soil_types"]:
        g = groups[s["group_code"]]
        obj = existing.get(s["zarc_code"]) or SoilType(zarc_code=s["zarc_code"])
        obj.group_code = s["group_code"]
        obj.name_technical = s["name_technical"]
        obj.name_simple = g["name_simple"]
        obj.description_simple = g["description_simple"]
        db.session.add(obj)
    db.session.commit()
    return len(data["soil_types"])


def seed_crops() -> tuple[int, int]:
    source_id = db.session.scalar(select(DataSource.id).where(DataSource.code == "plante_facil"))
    crops = {c.slug: c for c in db.session.scalars(select(Crop))}
    n_alias = 0
    for c in load_crops_yaml():
        crop = crops.get(c["slug"]) or Crop(slug=c["slug"])
        crop.official_name = c["official_name"]
        crop.scientific_name = c.get("scientific_name")
        crop.category = c.get("category")
        crop.mvp_enabled = True
        db.session.add(crop)
        db.session.flush()
        have = {
            (a.alias_normalized, a.region_scope_uf)
            for a in db.session.scalars(select(CropAlias).where(CropAlias.crop_id == crop.id))
        }
        entries = list(c.get("aliases", [])) + [{"alias": z, "kind": "zarc"} for z in c.get("zarc_names", [])]
        entries.append({"alias": c["slug"].replace("-", " "), "kind": "official"})
        for a in entries:
            key = (normalize_name(a["alias"]), a.get("uf"))
            if key in have:
                continue
            have.add(key)
            db.session.add(
                CropAlias(
                    crop_id=crop.id,
                    alias=a["alias"],
                    alias_normalized=key[0],
                    kind=a["kind"],
                    region_scope_uf=a.get("uf"),
                    source_id=source_id,
                    status="approved",
                    origin="seed",
                )
            )
            n_alias += 1
    db.session.commit()
    return len(load_crops_yaml()), n_alias
