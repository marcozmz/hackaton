"""Importador da Tábua de Risco do ZARC.

Formato real (dicionário de dados 2026): CSV `;` UTF-8 com BOM, uma linha por
cultura × município × solo × ciclo × manejo × clima × portaria e colunas dec1..dec36
com risco 0/20/30/40 (0 = não recomendado).

Estratégia: filtrar às culturas do MVP → despivotar (wide → long) → guardar só
decêndios com risco > 0. Vários arquivos (ex.: safra 2026/27 + perenes) entram na
mesma dataset_version. Idempotente pelo hash dos arquivos.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, func, insert, select

from app.extensions import db
from app.ingestion import base
from app.ingestion.catalog_seed import load_crops_yaml
from app.models import Crop, Municipality, SoilType, ZarcWindow, ZarcZone

DATASET = "zarc_tabua_risco"
DEC_COLS = [f"dec{i}" for i in range(1, 37)]
# Único lugar que conhece os nomes de coluna do arquivo oficial.
COLUMN_MAP = {
    "Nome_cultura": "zarc_crop_name",
    "SafraIni": "safra_ini",
    "SafraFin": "safra_fin",
    "Cod_Ciclo": "cycle_code",
    "Cod_Solo": "soil_code",
    "geocodigo": "municipality_ibge",
    "Cod_Clima": "climate_code",
    "Cod_Outros_Manejos": "management_code",
    "Portaria": "portaria",
    "Cod_NM": "management_level",
}
INT_COLS = ["cycle_code", "soil_code", "municipality_ibge", "climate_code", "management_code", "management_level"]
KEY = [
    "zarc_crop_name", "municipality_ibge", "soil_code", "cycle_code",
    "management_code", "management_level", "climate_code", "portaria",
]
VALID_RISK = {20, 30, 40}


def _crop_map(only: set[str] | None) -> dict[str, int]:
    ids = {c.slug: c.id for c in db.session.scalars(select(Crop))}
    out = {}
    for c in load_crops_yaml():
        if only and c["slug"] not in only:
            continue
        if c["slug"] not in ids:
            raise RuntimeError(f"cultura {c['slug']} não semeada — rode `flask data seed`")
        for name in c.get("zarc_names", []):
            out[name] = ids[c["slug"]]
    return out


def _season(ini, fin) -> str | None:
    try:
        i, f = int(ini), int(fin)
    except (TypeError, ValueError):
        return None
    return f"{i}/{f}" if i > 0 and f > 0 else None


def _discard_partial(version) -> None:
    zone_ids = select(ZarcZone.id).where(ZarcZone.dataset_version_id == version.id)
    db.session.execute(delete(ZarcWindow).where(ZarcWindow.zone_id.in_(zone_ids)))
    db.session.execute(delete(ZarcZone).where(ZarcZone.dataset_version_id == version.id))
    db.session.delete(version)
    db.session.commit()


def run(
    paths: list[Path],
    crops: set[str] | None = None,
    label: str | None = None,
    extracted_at: date | None = None,
    chunksize: int = 50_000,
) -> base.ImportReport:
    report = base.ImportReport(DATASET, [p.name for p in paths])
    ds = base.get_dataset(DATASET)
    sha = base.files_sha256(paths)
    if (v := base.existing_version(ds, sha)) is not None:
        if v.status in ("active", "superseded"):
            report.status, report.version_id = "unchanged", v.id
            return report
        _discard_partial(v)  # tentativa anterior falhou no meio: limpa e reimporta

    crop_map = _crop_map(crops)
    soil_map = {s.zarc_code: s.id for s in db.session.scalars(select(SoilType))}
    municipalities = set(db.session.scalars(select(Municipality.ibge_code)))
    if not municipalities:
        raise RuntimeError("sem municípios — rode `flask data import-municipios` antes")

    version = base.start_version(ds, label or "ZARC", paths, sha, extracted_at)
    next_id = (db.session.scalar(select(func.max(ZarcZone.id))) or 0) + 1
    seen: set[tuple] = set()
    seasons: set[str] = set()
    n_windows = 0
    found_crops: set[str] = set()
    try:
        for path in paths:
            reader = pd.read_csv(
                path, sep=";", encoding="utf-8-sig", dtype=str,
                usecols=list(COLUMN_MAP) + DEC_COLS, chunksize=chunksize,
            )
            for chunk in reader:
                report.rows_read += len(chunk)
                df = chunk.rename(columns=COLUMN_MAP)
                in_mvp = df.zarc_crop_name.isin(crop_map)
                report.skip("cultura_fora_do_mvp", int((~in_mvp).sum()))
                df = df[in_mvp].copy()
                if df.empty:
                    continue
                for c in INT_COLS:
                    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

                bad_mun = ~df.municipality_ibge.isin(municipalities)
                for code in df.loc[bad_mun, "municipality_ibge"].unique():
                    report.miss("municipio_ibge", int(code))
                report.skip("municipio_desconhecido", int(bad_mun.sum()))
                bad_soil = ~df.soil_code.isin(soil_map)
                for code in df.loc[bad_soil, "soil_code"].unique():
                    report.miss("solo", int(code))
                report.skip("solo_desconhecido", int((bad_soil & ~bad_mun).sum()))
                df = df[~bad_mun & ~bad_soil]

                df["portaria"] = df.portaria.fillna("")
                before = len(df)
                df = df.drop_duplicates(subset=KEY)
                report.skip("zona_duplicada", before - len(df))
                keys = list(df[KEY].itertuples(index=False, name=None))
                fresh = [k not in seen for k in keys]
                report.skip("zona_duplicada", len(fresh) - sum(fresh))
                df = df[fresh]
                seen.update(k for k, f in zip(keys, fresh) if f)
                if df.empty:
                    continue

                df["id"] = range(next_id, next_id + len(df))
                next_id += len(df)
                df["crop_id"] = df.zarc_crop_name.map(crop_map)
                df["soil_type_id"] = df.soil_code.map(soil_map)
                df["season_label"] = [_season(a, b) for a, b in zip(df.safra_ini, df.safra_fin)]
                seasons.update(s for s in df.season_label.unique() if s)
                found_crops.update(df.zarc_crop_name.unique())

                zones = pd.DataFrame(
                    {
                        "id": df.id,
                        "dataset_version_id": version.id,
                        "crop_id": df.crop_id,
                        "zarc_crop_name": df.zarc_crop_name,
                        "municipality_ibge": df.municipality_ibge,
                        "soil_type_id": df.soil_type_id,
                        "cycle_code": df.cycle_code,
                        "management_code": df.management_code,
                        "climate_code": df.climate_code,
                        "management_level": df.management_level,
                        "portaria": df.portaria.replace("", None),
                        "season_label": df.season_label,
                    }
                )
                db.session.execute(insert(ZarcZone), zones.to_dict("records"))

                long = df[["id", *DEC_COLS]].melt(id_vars="id", var_name="dec", value_name="risk")
                long["risk"] = pd.to_numeric(long.risk, errors="coerce").fillna(0).astype(int)
                invalid = (long.risk != 0) & ~long.risk.isin(VALID_RISK)
                report.skip("risco_invalido", int(invalid.sum()))
                long = long[long.risk.isin(VALID_RISK)]
                windows = pd.DataFrame(
                    {
                        "zone_id": long.id,
                        "decendio": long.dec.str[3:].astype(int),
                        "risk_pct": long.risk,
                    }
                )
                if not windows.empty:
                    db.session.execute(insert(ZarcWindow), windows.to_dict("records"))
                n_windows += len(windows)
                report.rows_loaded += len(df)
                db.session.commit()

        missing = set(crop_map) - found_crops
        if missing:
            report.extra["variantes_sem_linhas"] = ", ".join(sorted(missing))
        if report.rows_loaded == 0:
            raise RuntimeError("nenhuma zona carregada — confira --crops e os arquivos")
        if not label:
            version.version_label = "Safra " + " + ".join(sorted(seasons)) if seasons else "Sem safra"
        base.activate(version, report.rows_loaded)
        report.status, report.version_id = "active", version.id
        report.extra["janelas (decêndios recomendados)"] = n_windows
        report.extra["safras"] = ", ".join(sorted(seasons)) or "—"
    except Exception as e:
        base.fail(version, e)
        report.status = "failed"
        raise
    return report
