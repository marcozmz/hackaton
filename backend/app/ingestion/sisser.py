"""Importador do SISSER (PSR – Programa de Subvenção ao Seguro Rural), agregado na leitura.

A planilha oficial traz dados pessoais (nome e documento do segurado, coordenadas exatas,
números de proposta/apólice). Por isso:
- só as colunas de SAFE_COLUMNS são lidas — as pessoais nunca chegam à memória, ao banco ou ao log;
- agregamos por município × cultura × ano e gravamos só os totais;
- a supressão de células pequenas (k-anonimato) é aplicada na leitura da API, não aqui.
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
from app.models import Crop, InsuranceStat, Municipality

DATASET = "sisser"
SAFE_COLUMNS = {
    "NM_CULTURA_GLOBAL": "crop_name",
    "CD_GEOCMU": "municipality_ibge",
    "ANO_APOLICE": "year",
    "NR_AREA_TOTAL": "area_ha",
    "VL_LIMITE_GARANTIA": "insured_amount",
    "VL_PREMIO_LIQUIDO": "premium",
    "VL_SUBVENCAO_FEDERAL": "subsidy",
}
# Documentado para auditoria: colunas pessoais/identificadoras que NUNCA são lidas.
PERSONAL_COLUMNS = (
    "NM_SEGURADO", "NR_DOCUMENTO_SEGURADO", "LATITUDE", "LONGITUDE", "NR_DECIMAL_LATITUDE",
    "NR_DECIMAL_LONGITUDE", "NR_PROPOSTA", "ID_PROPOSTA", "NR_APOLICE",
)


def _crop_rules() -> list[tuple[int, list[str], list[str]]]:
    ids = {c.slug: c.id for c in db.session.scalars(select(Crop))}
    rules = []
    for c in load_crops_yaml():
        m = c.get("sisser_match") or {}
        if m.get("include"):
            rules.append(
                (ids[c["slug"]], [normalize_name(x) for x in m["include"]], [normalize_name(x) for x in m.get("exclude", [])])
            )
    return sorted(rules, key=lambda r: -max(len(i) for i in r[1]))


def _match(name: str, rules) -> int | None:
    n = normalize_name(name or "")
    for crop_id, inc, exc in rules:
        if any(n.startswith(i) for i in inc) and not any(e in n for e in exc):
            return crop_id
    return None


def _discard_partial(version) -> None:
    db.session.execute(delete(InsuranceStat).where(InsuranceStat.dataset_version_id == version.id))
    db.session.delete(version)
    db.session.commit()


def read_safe(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, usecols=list(SAFE_COLUMNS)).rename(columns=SAFE_COLUMNS)
    assert not set(PERSONAL_COLUMNS) & set(df.columns)
    return df


def run(paths: list[Path], extracted_at: date | None = None) -> base.ImportReport:
    report = base.ImportReport(DATASET, [p.name for p in paths])
    ds = base.get_dataset(DATASET)
    sha = base.files_sha256(paths)
    if (v := base.existing_version(ds, sha)) is not None:
        if v.status in ("active", "superseded"):
            report.status, report.version_id = "unchanged", v.id
            return report
        _discard_partial(v)

    rules = _crop_rules()
    municipalities = set(db.session.scalars(select(Municipality.ibge_code)))
    frames = [read_safe(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    report.rows_read = len(df)

    df["municipality_ibge"] = pd.to_numeric(df.municipality_ibge, errors="coerce")
    bad = df.municipality_ibge.isna() | ~df.municipality_ibge.isin(municipalities)
    report.skip("municipio_invalido", int(bad.sum()))
    df = df[~bad].copy()
    df["municipality_ibge"] = df.municipality_ibge.astype(int)
    for c in ("area_ha", "insured_amount", "premium", "subsidy"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    names = {n: _match(n, rules) for n in df.crop_name.dropna().unique()}
    df["crop_id"] = df.crop_name.map(names)
    years = sorted(int(y) for y in df.year.unique())

    agg = {"policies_count": ("crop_name", "size"), "insured_area_ha": ("area_ha", "sum"),
           "insured_amount": ("insured_amount", "sum"), "premium_total": ("premium", "sum"),
           "subsidy_total": ("subsidy", "sum")}
    by_crop = df[df.crop_id.notna()].groupby(["municipality_ibge", "crop_id", "year"], as_index=False).agg(**agg)
    by_mun = df.groupby(["municipality_ibge", "year"], as_index=False).agg(**agg)
    by_mun["crop_id"] = None

    version = base.start_version(ds, f"PSR {', '.join(map(str, years))}", paths, sha, extracted_at)
    try:
        rows = []
        for frame in (by_crop, by_mun):
            for r in frame.itertuples(index=False):
                rows.append(
                    {
                        "dataset_version_id": version.id,
                        "municipality_ibge": int(r.municipality_ibge),
                        "crop_id": int(r.crop_id) if r.crop_id is not None and r.crop_id == r.crop_id else None,
                        "year": int(r.year),
                        "policies_count": int(r.policies_count),
                        "insured_area_ha": round(float(r.insured_area_ha), 2),
                        "insured_amount": round(float(r.insured_amount), 2),
                        "premium_total": round(float(r.premium_total), 2),
                        "subsidy_total": round(float(r.subsidy_total), 2),
                    }
                )
        for i in range(0, len(rows), 5000):
            db.session.execute(insert(InsuranceStat), rows[i : i + 5000])
        db.session.commit()
        report.rows_loaded = len(rows)
        report.extra["anos"] = ", ".join(map(str, years))
        report.extra["culturas do MVP encontradas"] = ", ".join(sorted(n for n, cid in names.items() if cid)) or "—"
        report.extra["apólices agregadas"] = len(df)
        base.activate(version, len(rows))
        report.status, report.version_id = "active", version.id
    except Exception as e:
        base.fail(version, e)
        report.status = "failed"
        raise
    return report
