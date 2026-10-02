"""Provenance — de onde veio cada dado."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataSource(db.Model):
    __tablename__ = "data_source"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str | None] = mapped_column(String(200))
    homepage_url: Mapped[str | None] = mapped_column(String(500))
    license: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="source")


class Dataset(db.Model):
    __tablename__ = "dataset"
    __table_args__ = (
        CheckConstraint("usage_status IN ('active','reserve','blocked')", name="usage_status"),
        CheckConstraint("sensitivity IN ('none','personal_data_risk')", name="sensitivity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id"))
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    format: Mapped[str] = mapped_column(String(20))
    methodology_url: Mapped[str | None] = mapped_column(String(500))
    refresh_policy: Mapped[str | None] = mapped_column(String(120))
    usage_status: Mapped[str] = mapped_column(String(20), default="active")
    sensitivity: Mapped[str] = mapped_column(String(30), default="none")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[DataSource] = relationship(back_populates="datasets")
    versions: Mapped[list["DatasetVersion"]] = relationship(back_populates="dataset")


class DatasetVersion(db.Model):
    __tablename__ = "dataset_version"
    __table_args__ = (
        UniqueConstraint("dataset_id", "file_sha256", name="uq_dataset_version_sha"),
        CheckConstraint("status IN ('importing','active','superseded','failed')", name="status"),
        Index(
            "uq_dataset_version_current",
            "dataset_id",
            unique=True,
            sqlite_where=text("is_current = 1"),
            postgresql_where=text("is_current"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"))
    version_label: Mapped[str] = mapped_column(String(120))
    extracted_at: Mapped[date] = mapped_column(Date)
    published_at: Mapped[date | None] = mapped_column(Date)
    file_name: Mapped[str] = mapped_column(String(500))
    file_sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="importing")
    is_current: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
