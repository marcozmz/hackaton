from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select

from app.extensions import db
from app.models import ForecastDaily, ForecastRun
from app.providers.weather.base import ForecastDTO


def latest(municipality_ibge: int) -> ForecastRun | None:
    q = (
        select(ForecastRun)
        .where(ForecastRun.municipality_ibge == municipality_ibge)
        .order_by(ForecastRun.fetched_at.desc())
        .limit(1)
    )
    return db.session.scalar(q)


def save(municipality_ibge: int, dto: ForecastDTO, fetched_at: datetime, valid_until: datetime) -> ForecastRun:
    raw = json.dumps(dto.raw, sort_keys=True, default=str) if dto.raw else repr(dto.days)
    run = ForecastRun(
        provider=dto.provider,
        municipality_ibge=municipality_ibge,
        lat=dto.lat,
        lon=dto.lon,
        issued_at=dto.issued_at,
        fetched_at=fetched_at,
        valid_until=valid_until,
        payload_hash=hashlib.sha256(raw.encode()).hexdigest(),
        raw_json=None,  # bruto só para debug; não guardamos por padrão
    )
    run.days = [
        ForecastDaily(
            date=d.date, t_min=d.t_min, t_max=d.t_max, precip_mm=d.precip_mm,
            precip_prob=d.precip_prob, wind_max_kmh=d.wind_max_kmh, et0_mm=d.et0_mm,
        )
        for d in dto.days
    ]
    db.session.add(run)
    db.session.commit()
    return run
