"""Farmer — conta, propriedade e lavouras. Minimização (LGPD): só o necessário.

Não guardamos CPF, telefone, endereço, coordenadas exatas nem dados socioeconômicos (Pronaf/DAP).
Nome é só "como quer ser chamado". Excluir a conta apaga tudo (cascata).
"""
from __future__ import annotations

import uuid
import datetime as dt
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.provenance import utcnow


def new_id() -> str:
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint("language_level IN ('simple','standard','technical')", name="language_level"),
        CheckConstraint("theme IN ('light','dark')", name="theme"),
        CheckConstraint("font_size IN ('normal','grande','muito-grande')", name="font_size"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    language_level: Mapped[str] = mapped_column(String(10), default="simple")
    theme: Mapped[str] = mapped_column(String(10), default="light")
    font_size: Mapped[str] = mapped_column(String(15), default="grande")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Opt-in (LGPD): quando aceitou receber o aviso diário por e-mail. None = não recebe.
    email_alerts_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    farms: Mapped[list["Farm"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[list["FarmTask"]] = relationship(cascade="all, delete-orphan")

    @property
    def farm(self) -> "Farm | None":
        return self.farms[0] if self.farms else None


class Farm(db.Model):
    __tablename__ = "farm"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(80))
    municipality_ibge: Mapped[int] = mapped_column(ForeignKey("municipality.ibge_code"))
    area_ha: Mapped[float | None] = mapped_column(Float)
    soil_group: Mapped[int | None] = mapped_column(SmallInteger)  # 1 areia · 2 meio-termo · 3 barro · None = não sei
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="farms")
    plantings: Mapped[list["Planting"]] = relationship(back_populates="farm", cascade="all, delete-orphan")


class Planting(db.Model):
    """Cultura que o agricultor planta/pretende plantar na propriedade."""

    __tablename__ = "planting"
    __table_args__ = (
        UniqueConstraint("farm_id", "crop_id", name="uq_planting_farm_crop"),
        CheckConstraint("stage IN ('planning','planted','growing','harvested')", name="stage"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farm.id", ondelete="CASCADE"), index=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    stage: Mapped[str] = mapped_column(String(12), default="planning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    farm: Mapped[Farm] = relationship(back_populates="plantings")


class FarmTask(db.Model):
    """Atividade do agricultor no calendário de planejamento (só o que ele escreve)."""

    __tablename__ = "farm_task"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    on_date: Mapped[dt.date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(120))
    crop_id: Mapped[int | None] = mapped_column(ForeignKey("crop.id"))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
