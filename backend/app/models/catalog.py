"""Catalog — o que se planta, como se chama e onde a cultivar é indicada."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.provenance import utcnow


class Crop(db.Model):
    __tablename__ = "crop"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    official_name: Mapped[str] = mapped_column(String(120))
    scientific_name: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(40))
    mvp_enabled: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    aliases: Mapped[list["CropAlias"]] = relationship(back_populates="crop")


class CropAlias(db.Model):
    __tablename__ = "crop_alias"
    __table_args__ = (
        UniqueConstraint("crop_id", "alias_normalized", "region_scope_uf", name="uq_crop_alias"),
        CheckConstraint(
            "kind IN ('official','common','regional','scientific','abbreviation','misspelling','zarc')",
            name="kind",
        ),
        CheckConstraint("status IN ('approved','suggested','rejected')", name="status"),
        CheckConstraint("origin IN ('seed','import','ai_suggestion','admin')", name="origin"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    alias: Mapped[str] = mapped_column(String(120))
    alias_normalized: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    region_scope_uf: Mapped[str | None] = mapped_column(String(2))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id"))
    status: Mapped[str] = mapped_column(String(20), default="approved")
    origin: Mapped[str] = mapped_column(String(20), default="seed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    crop: Mapped[Crop] = relationship(back_populates="aliases")


class SoilType(db.Model):
    """Código de solo do ZARC.

    1–3: classes texturais (arenoso, textura média, argiloso).
    11–16: classes de água disponível AD1–AD6 (metodologia nova do ZARC).
    `group_code` agrupa tudo nas 3 opções simples que o agricultor escolhe.
    """

    __tablename__ = "soil_type"
    id: Mapped[int] = mapped_column(primary_key=True)
    zarc_code: Mapped[int] = mapped_column(unique=True)
    group_code: Mapped[int]  # 1 areia · 2 meio-termo · 3 barro
    name_simple: Mapped[str] = mapped_column(String(80))
    name_technical: Mapped[str] = mapped_column(String(80))
    description_simple: Mapped[str | None] = mapped_column(Text)


class CropVariety(db.Model):
    __tablename__ = "crop_variety"
    __table_args__ = (UniqueConstraint("crop_id", "name_normalized", name="uq_crop_variety"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    name: Mapped[str] = mapped_column(String(160))
    name_normalized: Mapped[str] = mapped_column(String(160))
    holder: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


class VarietyZone(db.Model):
    """Onde a cultivar é indicada (ZARC – Cultivares). O arquivo oficial vem por UF + grupo."""

    __tablename__ = "variety_zone"
    __table_args__ = (
        Index("ix_variety_zone_lookup", "dataset_version_id", "uf"),
        UniqueConstraint(
            "dataset_version_id", "variety_id", "uf", "group_code", "zarc_crop_name", name="uq_variety_zone"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_version.id"))
    variety_id: Mapped[int] = mapped_column(ForeignKey("crop_variety.id"))
    zarc_crop_name: Mapped[str] = mapped_column(String(160))
    uf: Mapped[str] = mapped_column(ForeignKey("state.uf"))
    municipality_ibge: Mapped[int | None] = mapped_column(ForeignKey("municipality.ibge_code"))
    soil_type_id: Mapped[int | None] = mapped_column(ForeignKey("soil_type.id"))
    group_code: Mapped[str | None] = mapped_column(String(20))
    season_label: Mapped[str | None] = mapped_column(String(20))
    adaptation_region: Mapped[str | None] = mapped_column(String(60))

    variety: Mapped[CropVariety] = relationship()
