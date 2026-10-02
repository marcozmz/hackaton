from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select

from app.extensions import db
from app.models import Municipality


def get(ibge_code: int) -> Municipality | None:
    return db.session.get(Municipality, ibge_code)


def by_name(name_normalized: str, uf: str | None = None) -> list[Municipality]:
    q = select(Municipality).where(Municipality.name_normalized == name_normalized)
    if uf:
        q = q.where(Municipality.uf == uf)
    return list(db.session.scalars(q))


def search(prefix_normalized: str, uf: str | None = None, limit: int = 20) -> list[Municipality]:
    escaped = prefix_normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    q = select(Municipality).where(Municipality.name_normalized.like(f"{escaped}%", escape="\\"))
    if uf:
        q = q.where(Municipality.uf == uf)
    return list(db.session.scalars(q.order_by(Municipality.name).limit(limit)))


@lru_cache(maxsize=1)
def all_light() -> tuple[tuple[int, str, str, str, float, float], ...]:
    """(ibge, nome, nome_norm, uf, lat, lon) de todos os municípios — ~5,5 mil, cache em memória."""
    rows = db.session.execute(
        select(
            Municipality.ibge_code, Municipality.name, Municipality.name_normalized,
            Municipality.uf, Municipality.centroid_lat, Municipality.centroid_lon,
        )
    )
    return tuple(tuple(r) for r in rows)
