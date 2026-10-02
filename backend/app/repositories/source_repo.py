from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import DataSource, Dataset, DatasetVersion


def datasets_with_current_version() -> list[tuple[Dataset, DataSource, DatasetVersion | None]]:
    q = (
        select(Dataset, DataSource, DatasetVersion)
        .join(DataSource, DataSource.id == Dataset.source_id)
        .outerjoin(
            DatasetVersion,
            (DatasetVersion.dataset_id == Dataset.id) & (DatasetVersion.is_current.is_(True)),
        )
        .order_by(Dataset.id)
    )
    return [tuple(r) for r in db.session.execute(q)]


def versions(dataset_code: str | None = None) -> list[tuple[Dataset, DatasetVersion]]:
    q = select(Dataset, DatasetVersion).join(DatasetVersion, DatasetVersion.dataset_id == Dataset.id)
    if dataset_code:
        q = q.where(Dataset.code == dataset_code)
    return [tuple(r) for r in db.session.execute(q.order_by(Dataset.code, DatasetVersion.id))]
