"""Malhas municipais do IBGE (GeoJSON simplificado, qualidade mínima), um arquivo por UF.

Geometria fica em arquivo estático (não no banco, sem PostGIS no MVP — files/12-map-and-geospatial.md).
A simplificação já vem do IBGE (`qualidade=minima`), então nunca simplificamos em request.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

import requests
from sqlalchemy import select

from app.extensions import db
from app.ingestion import base
from app.models import State

log = logging.getLogger(__name__)

DATASET = "ibge_malha_municipal"
URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
    "?intrarregiao=municipio&formato=application/vnd.geo%2Bjson&qualidade=minima"
)


def _download(uf: str, dest: Path, retries: int = 3) -> int:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(URL.format(uf=uf), timeout=(10, 120))
            resp.raise_for_status()
            data = resp.json()
            if data.get("type") != "FeatureCollection" or not data.get("features"):
                raise ValueError("resposta sem features")
            dest.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            return len(data["features"])
        except (requests.RequestException, ValueError) as e:
            last = e
            log.warning("malha %s falhou (tentativa %s): %s", uf, attempt + 1, type(e).__name__)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"não consegui baixar a malha de {uf}") from last


def run(geo_dir: Path, ufs: list[str] | None = None, extracted_at: date | None = None) -> base.ImportReport:
    geo_dir.mkdir(parents=True, exist_ok=True)
    all_ufs = sorted(db.session.scalars(select(State.uf)))
    targets = [u.upper() for u in ufs] if ufs else all_ufs
    report = base.ImportReport(DATASET, [f"{u}.geojson" for u in targets])
    for uf in targets:
        dest = geo_dir / f"{uf}.geojson"
        if dest.exists() and dest.stat().st_size > 0:
            report.skip("ja_baixado")
            continue
        n = _download(uf, dest)
        report.rows_loaded += n
        report.rows_read += n

    files = sorted(geo_dir.glob("*.geojson"))
    ds = base.get_dataset(DATASET)
    sha = base.files_sha256(files)
    if (v := base.existing_version(ds, sha)) is not None:
        report.status, report.version_id = "unchanged", v.id
        return report
    version = base.start_version(ds, f"IBGE malha municipal (mínima) · {len(files)} UFs", files, sha, extracted_at)
    total = sum(len(json.loads(f.read_text(encoding="utf-8"))["features"]) for f in files)
    base.activate(version, total)
    report.status, report.version_id = "active", version.id
    report.extra["municípios com limite"] = total
    return report
