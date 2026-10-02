"""Territory — onde fica o agricultor. Código IBGE é a chave universal."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class State(db.Model):
    __tablename__ = "state"
    uf: Mapped[str] = mapped_column(String(2), primary_key=True)
    ibge_code: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(60))
    macro_region: Mapped[str] = mapped_column(String(20))


class Municipality(db.Model):
    __tablename__ = "municipality"
    __table_args__ = (Index("ix_municipality_uf_name", "uf", "name_normalized"),)
    ibge_code: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(120))
    name_normalized: Mapped[str] = mapped_column(String(120), index=True)
    uf: Mapped[str] = mapped_column(ForeignKey("state.uf"))
    centroid_lat: Mapped[float]
    centroid_lon: Mapped[float]

    state: Mapped[State] = relationship()
