"""Contrato comum dos importadores: versionar, validar, trocar is_current numa transação."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select, update

from app.extensions import db
from app.models import Dataset, DatasetVersion

log = logging.getLogger(__name__)


@dataclass
class ImportReport:
    dataset: str
    files: list[str]
    rows_read: int = 0
    rows_loaded: int = 0
    rows_skipped: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)
    unmatched: dict[str, set] = field(default_factory=dict)
    extra: dict[str, object] = field(default_factory=dict)
    version_id: int | None = None
    status: str = "pending"

    def skip(self, reason: str, n: int = 1) -> None:
        self.rows_skipped += n
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + n

    def miss(self, kind: str, value) -> None:
        self.unmatched.setdefault(kind, set()).add(value)

    def render(self) -> str:
        lines = [
            f"[{self.dataset}] status={self.status} versão={self.version_id}",
            f"  arquivos: {', '.join(self.files)}",
            f"  lidas={self.rows_read} carregadas={self.rows_loaded} descartadas={self.rows_skipped}",
        ]
        for k, v in sorted(self.skipped_reasons.items(), key=lambda kv: -kv[1]):
            lines.append(f"    - {k}: {v}")
        for k, vals in self.unmatched.items():
            sample = ", ".join(sorted(map(str, vals))[:15])
            lines.append(f"  não casados ({k}): {len(vals)} → {sample}{' …' if len(vals) > 15 else ''}")
        for k, v in self.extra.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


def files_sha256(paths: list[Path]) -> str:
    """Hash combinado de vários arquivos (ordem estável) → idempotência."""
    combined = hashlib.sha256()
    for p in sorted(paths, key=lambda x: x.name):
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        combined.update(h.hexdigest().encode())
    return combined.hexdigest()


def get_dataset(code: str) -> Dataset:
    ds = db.session.scalar(select(Dataset).where(Dataset.code == code))
    if ds is None:
        raise RuntimeError(f"dataset '{code}' não existe — rode `flask data seed` antes")
    return ds


def existing_version(dataset: Dataset, sha: str) -> DatasetVersion | None:
    return db.session.scalar(
        select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id, DatasetVersion.file_sha256 == sha)
    )


def start_version(dataset: Dataset, label: str, paths: list[Path], sha: str, extracted_at: date | None) -> DatasetVersion:
    extracted = extracted_at or min(datetime.fromtimestamp(p.stat().st_mtime).date() for p in paths)
    v = DatasetVersion(
        dataset_id=dataset.id,
        version_label=label,
        extracted_at=extracted,
        file_name=" + ".join(p.name for p in paths),
        file_sha256=sha,
        status="importing",
        is_current=False,
    )
    db.session.add(v)
    db.session.commit()
    return v


def activate(version: DatasetVersion, row_count: int) -> None:
    """Swap atômico: anterior vira superseded, nova vira corrente."""
    db.session.execute(
        update(DatasetVersion)
        .where(DatasetVersion.dataset_id == version.dataset_id, DatasetVersion.is_current.is_(True))
        .values(is_current=False, status="superseded")
    )
    version.row_count = row_count
    version.status = "active"
    version.is_current = True
    db.session.commit()


def fail(version: DatasetVersion, error: Exception) -> None:
    db.session.rollback()
    version.status = "failed"
    version.notes = f"{type(error).__name__}: {error}"[:2000]
    db.session.commit()
