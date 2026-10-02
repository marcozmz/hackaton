"""Seguro rural (SISSER/PSR) — SOMENTE agregados. Nunca linha individual (files/09-security.md).

crop_id NULL = total do município (todas as culturas).
"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class InsuranceStat(db.Model):
    __tablename__ = "insurance_stat"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "municipality_ibge", "crop_id", "year", name="uq_insurance_stat"),
        Index("ix_insurance_stat_lookup", "municipality_ibge", "crop_id", "year"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_version.id"))
    municipality_ibge: Mapped[int] = mapped_column(ForeignKey("municipality.ibge_code"))
    crop_id: Mapped[int | None] = mapped_column(ForeignKey("crop.id"))
    year: Mapped[int] = mapped_column(SmallInteger)
    policies_count: Mapped[int]
    insured_area_ha: Mapped[float] = mapped_column(Float)
    insured_amount: Mapped[float] = mapped_column(Float)  # limite de garantia (R$)
    premium_total: Mapped[float] = mapped_column(Float)  # prêmio líquido (R$)
    subsidy_total: Mapped[float] = mapped_column(Float)  # subvenção federal (R$)
