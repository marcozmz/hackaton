"""ZARC em formato longo: só decêndios com risco aceitável viram linha.

Semântica:
- existe `zarc_zone` mas não há `zarc_window` no decêndio ⇒ plantio não recomendado;
- não existe `zarc_zone` para (município, cultura) ⇒ sem zoneamento (no_data).
"""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class ZarcZone(db.Model):
    __tablename__ = "zarc_zone"
    __table_args__ = (
        Index("ix_zarc_zone_lookup", "municipality_ibge", "crop_id", "dataset_version_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_version.id"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    zarc_crop_name: Mapped[str] = mapped_column(String(160))  # ex.: "Milho 2ª Safra"
    municipality_ibge: Mapped[int] = mapped_column(ForeignKey("municipality.ibge_code"))
    soil_type_id: Mapped[int] = mapped_column(ForeignKey("soil_type.id"))
    cycle_code: Mapped[int] = mapped_column(SmallInteger)
    management_code: Mapped[int] = mapped_column(SmallInteger)  # 1 sequeiro · 2 irrigado · 3 irrigado c/ geada
    climate_code: Mapped[int] = mapped_column(SmallInteger, default=0)
    management_level: Mapped[int] = mapped_column(SmallInteger, default=0)  # Cod_NM: NM1–NM4 (soja); 0 = n/a
    portaria: Mapped[str | None] = mapped_column(String(80))
    season_label: Mapped[str | None] = mapped_column(String(20))  # "2026/2027"


class ZarcWindow(db.Model):
    __tablename__ = "zarc_window"
    __table_args__ = (
        CheckConstraint("decendio BETWEEN 1 AND 36", name="decendio"),
        CheckConstraint("risk_pct IN (20, 30, 40)", name="risk_pct"),
        {"sqlite_with_rowid": False},
    )
    zone_id: Mapped[int] = mapped_column(ForeignKey("zarc_zone.id"), primary_key=True)
    decendio: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    risk_pct: Mapped[int] = mapped_column(SmallInteger)
