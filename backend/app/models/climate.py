"""Climate — previsão versionada por execução (nunca sobrescreve).

"Previsão atual" = último forecast_run do município com valid_until > agora.
Runs antigos ficam (auditoria: recomendações citam o run).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class ForecastRun(db.Model):
    __tablename__ = "forecast_run"
    __table_args__ = (Index("ix_forecast_run_lookup", "municipality_ibge", "fetched_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    municipality_ibge: Mapped[int] = mapped_column(ForeignKey("municipality.ibge_code"))
    lat: Mapped[float]
    lon: Mapped[float]
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_hash: Mapped[str] = mapped_column(String(64))
    raw_json: Mapped[dict | None] = mapped_column(JSON)

    days: Mapped[list["ForecastDaily"]] = relationship(order_by="ForecastDaily.date", cascade="all, delete-orphan")


class ForecastDaily(db.Model):
    __tablename__ = "forecast_daily"
    run_id: Mapped[int] = mapped_column(ForeignKey("forecast_run.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    t_min: Mapped[float | None] = mapped_column(Float)
    t_max: Mapped[float | None] = mapped_column(Float)
    precip_mm: Mapped[float | None] = mapped_column(Float)
    precip_prob: Mapped[int | None] = mapped_column(SmallInteger)
    wind_max_kmh: Mapped[float | None] = mapped_column(Float)
    et0_mm: Mapped[float | None] = mapped_column(Float)
