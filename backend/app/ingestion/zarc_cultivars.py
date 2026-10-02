"""Importador do ZARC – Cultivares (siszarc_cronograma.csv.gz).

Formato real: `;` UTF-8 BOM, colunas Safra, Cultura, Obtentor_Mantenedor, Cultivar,
UF, Grupo, Regiao_de_Adaptacao. Granularidade: **UF + grupo** (sem município) —
por isso variety_zone.municipality_ibge fica nulo e a resposta marca `cultivar_by_uf`.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, insert, select

from app.domain.text import normalize_name
from app.extensions import db
from app.ingestion import base
from app.ingestion.catalog_seed import load_crops_yaml
from app.models import Crop, CropVariety, State, VarietyZone

DATASET = "zarc_cultivares"
COLUMN_MAP = {
    "Safra": "season",
    "Cultura": "zarc_crop_name",
    "Obtentor_Mantenedor": "holder",
    "Cultivar": "variety",
    "UF": "uf",
    "Grupo": "group_code",
    "Regiao_de_Adaptacao": "adaptation_region",
}


def match_crop(name: str, rules: list[tuple[int, list[str], list[str]]]) -> int | None:
    n = normalize_name(name)
    for crop_id, include, exclude in rules:
        if any(n.startswith(i) for i in include) and not any(e in n for e in exclude):
            return crop_id
    return None


def _rules(only: set[str] | None) -> list[tuple[int, list[str], list[str]]]:
    ids = {c.slug: c.id for c in db.session.scalars(select(Crop))}
    rules = []
    for c in load_crops_yaml():
        if only and c["slug"] not in only:
            continue
        m = c.get("cultivar_match") or {}
        rules.append(
            (ids[c["slug"]], [normalize_name(x) for x in m.get("include", [])], [normalize_name(x) for x in m.get("exclude", [])])
        )
    # regras mais específicas primeiro (ex.: "feijao caupi" antes de "feijao")
    return sorted(rules, key=lambda r: -max((len(i) for i in r[1]), default=0))


def _discard_partial(version) -> None:
    db.session.execute(delete(VarietyZone).where(VarietyZone.dataset_version_id == version.id))
    db.session.delete(version)
    db.session.commit()


def run(
    path: Path,
    seasons: list[str] | None = None,
    crops: set[str] | None = None,
    extracted_at: date | None = None,
    chunksize: int = 200_000,
) -> base.ImportReport:
    """`seasons`: ex. ["2026-2027"]. Padrão: a safra mais recente presente no arquivo."""
    report = base.ImportReport(DATASET, [path.name])
    ds = base.get_dataset(DATASET)
    sha = base.files_sha256([path])
    if (v := base.existing_version(ds, sha)) is not None:
        if v.status in ("active", "superseded"):
            report.status, report.version_id = "unchanged", v.id
            return report
        _discard_partial(v)

    rules = _rules(crops)
    ufs = set(db.session.scalars(select(State.uf)))
    opts = dict(sep=";", encoding="utf-8-sig", dtype=str, chunksize=chunksize)

    if not seasons:
        all_seasons: set[str] = set()
        for ch in pd.read_csv(path, usecols=["Safra"], **opts):
            all_seasons.update(ch.Safra.dropna().unique())
        seasons = [max(all_seasons)]
    report.extra["safras"] = ", ".join(seasons)

    version = base.start_version(ds, f"Cultivares safra {', '.join(seasons)}", [path], sha, extracted_at)
    try:
        varieties = {
            (v.crop_id, v.name_normalized): v.id for v in db.session.scalars(select(CropVariety))
        }
        crop_cache: dict[str, int | None] = {}
        seen: set[tuple] = set()
        for chunk in pd.read_csv(path, usecols=list(COLUMN_MAP), **opts):
            report.rows_read += len(chunk)
            df = chunk.rename(columns=COLUMN_MAP)
            df = df[df.season.isin(seasons)]
            report.skip("outra_safra", len(chunk) - len(df))
            for r in df.itertuples(index=False):
                if r.zarc_crop_name not in crop_cache:
                    crop_cache[r.zarc_crop_name] = match_crop(r.zarc_crop_name, rules)
                crop_id = crop_cache[r.zarc_crop_name]
                if crop_id is None:
                    report.skip("cultura_fora_do_mvp")
                    continue
                if r.uf not in ufs or not isinstance(r.variety, str):
                    report.skip("uf_ou_cultivar_invalido")
                    continue
                vkey = (crop_id, normalize_name(r.variety))
                if vkey not in varieties:
                    obj = CropVariety(
                        crop_id=crop_id, name=r.variety.strip(), name_normalized=vkey[1],
                        holder=r.holder if isinstance(r.holder, str) else None,
                    )
                    db.session.add(obj)
                    db.session.flush()
                    varieties[vkey] = obj.id
                group = r.group_code if isinstance(r.group_code, str) else None
                zkey = (varieties[vkey], r.uf, group, r.zarc_crop_name)
                if zkey in seen:
                    report.skip("duplicada")
                    continue
                seen.add(zkey)
                report.rows_loaded += 1
            db.session.flush()

        rows = [
            {
                "dataset_version_id": version.id,
                "variety_id": vid,
                "uf": uf,
                "group_code": grp,
                "zarc_crop_name": cname,
                "season_label": ", ".join(seasons),
            }
            for vid, uf, grp, cname in seen
        ]
        for i in range(0, len(rows), 20_000):
            db.session.execute(insert(VarietyZone), rows[i : i + 20_000])
        db.session.commit()
        matched = sorted(k for k, v in crop_cache.items() if v)
        report.extra["culturas casadas"] = ", ".join(matched) or "—"
        if report.rows_loaded == 0:
            raise RuntimeError("nenhuma cultivar carregada — confira cultivar_match em crops.yaml")
        base.activate(version, report.rows_loaded)
        report.status, report.version_id = "active", version.id
    except Exception as e:
        base.fail(version, e)
        report.status = "failed"
        raise
    return report
