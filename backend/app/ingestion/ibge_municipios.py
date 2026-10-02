"""Estados + municípios com centroide (sem eles não há localização)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.domain.text import normalize_name
from app.extensions import db
from app.ingestion import base
from app.models import Municipality, State

DATASET = "ibge_municipios"


def run(municipios: Path, estados: Path, extracted_at: date | None = None) -> base.ImportReport:
    report = base.ImportReport(DATASET, [municipios.name, estados.name])
    ds = base.get_dataset(DATASET)
    sha = base.files_sha256([municipios, estados])
    if base.existing_version(ds, sha):
        report.status = "unchanged"
        return report

    est = pd.read_csv(estados, encoding="utf-8-sig", dtype={"codigo_uf": int})
    mun = pd.read_csv(municipios, encoding="utf-8-sig", dtype={"codigo_ibge": int, "codigo_uf": int})
    uf_by_code = dict(zip(est.codigo_uf, est.uf))
    report.rows_read = len(mun)

    version = base.start_version(ds, "IBGE municípios (kelvins)", [municipios, estados], sha, extracted_at)
    try:
        # PK natural (código IBGE): recarga atualiza no lugar, nunca apaga (zarc_zone referencia).
        existing_states = {s.uf for s in db.session.scalars(select(State))}
        for r in est.itertuples():
            if r.uf not in existing_states:
                db.session.add(State(uf=r.uf, ibge_code=r.codigo_uf, name=r.nome, macro_region=r.regiao))
        db.session.flush()

        existing = {m.ibge_code: m for m in db.session.scalars(select(Municipality))}
        for r in mun.itertuples():
            uf = uf_by_code.get(r.codigo_uf)
            if not uf:
                report.skip("uf_desconhecida")
                continue
            m = existing.get(r.codigo_ibge) or Municipality(ibge_code=r.codigo_ibge)
            m.name, m.name_normalized, m.uf = r.nome, normalize_name(r.nome), uf
            m.centroid_lat, m.centroid_lon = float(r.latitude), float(r.longitude)
            db.session.add(m)
            report.rows_loaded += 1
        db.session.commit()
        base.activate(version, report.rows_loaded)
        report.status, report.version_id = "active", version.id
    except Exception as e:
        base.fail(version, e)
        report.status = "failed"
        raise
    return report
