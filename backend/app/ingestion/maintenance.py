"""Manutenção do banco: podar versões antigas e empacotar/restaurar o banco pronto para a equipe."""
from __future__ import annotations

import sqlite3
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import delete, select

from app.extensions import db
from app.models import DatasetVersion, InsuranceStat, VarietyZone, ZarcWindow, ZarcZone


def prune_superseded() -> dict:
    """Apaga os DADOS das versões não vigentes (o registro em dataset_version fica, para auditoria)."""
    old = list(db.session.scalars(select(DatasetVersion).where(DatasetVersion.is_current.is_(False))))
    ids = [v.id for v in old]
    if not ids:
        return {"versions": 0}
    zone_ids = select(ZarcZone.id).where(ZarcZone.dataset_version_id.in_(ids))
    w = db.session.execute(delete(ZarcWindow).where(ZarcWindow.zone_id.in_(zone_ids))).rowcount
    z = db.session.execute(delete(ZarcZone).where(ZarcZone.dataset_version_id.in_(ids))).rowcount
    vz = db.session.execute(delete(VarietyZone).where(VarietyZone.dataset_version_id.in_(ids))).rowcount
    ins = db.session.execute(delete(InsuranceStat).where(InsuranceStat.dataset_version_id.in_(ids))).rowcount
    for v in old:
        if v.status == "superseded":
            v.notes = ((v.notes or "") + " | dados podados (prune)").strip(" |")
    db.session.commit()
    return {"versions": len(ids), "zarc_window": w, "zarc_zone": z, "variety_zone": vz, "insurance_stat": ins}


def _sqlite_path() -> Path:
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database:
        raise RuntimeError("export/import do banco só vale para SQLite")
    return Path(url.database)


def export_db(out_zip: Path, geo_dir: Path | None = None) -> dict:
    """Cópia compacta (VACUUM INTO) do SQLite + malhas do mapa, num .zip para compartilhar."""
    src = _sqlite_path()
    with tempfile.TemporaryDirectory() as tmp:
        compact = Path(tmp) / "plantefacil.db"
        con = sqlite3.connect(src)
        con.execute(f"VACUUM INTO '{compact.as_posix()}'")
        con.close()
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(compact, "plantefacil.db")
            if geo_dir and geo_dir.exists():
                for f in sorted(geo_dir.glob("*.geojson")):
                    zf.write(f, f"geo/{f.name}")
        db_mb = compact.stat().st_size / 1e6
    return {"db_mb": round(db_mb), "zip_mb": round(out_zip.stat().st_size / 1e6), "file": str(out_zip)}


def import_db(zip_path: Path, instance_dir: Path) -> dict:
    """Restaura o pacote gerado por export_db em backend/instance (substitui o banco local)."""
    instance_dir.mkdir(parents=True, exist_ok=True)
    target = instance_dir / "plantefacil.db"
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(target) + suffix)
        if p.exists():
            p.unlink()
    with zipfile.ZipFile(zip_path) as zf:
        zf.extract("plantefacil.db", instance_dir)
        geo = [n for n in zf.namelist() if n.startswith("geo/")]
        for n in geo:
            zf.extract(n, instance_dir)
    return {"db": str(target), "geo_files": len(geo)}
