"""Leitura dos agregados do SISSER, sempre na versão corrente."""
from __future__ import annotations

from sqlalchemy import func, select

from app.extensions import db
from app.models import DatasetVersion, InsuranceStat, Municipality
from app.repositories.catalog_repo import current_version

DATASET = "sisser"
SUM_COLS = (
    func.sum(InsuranceStat.policies_count),
    func.sum(InsuranceStat.insured_area_ha),
    func.sum(InsuranceStat.insured_amount),
    func.sum(InsuranceStat.premium_total),
    func.sum(InsuranceStat.subsidy_total),
)


def current() -> DatasetVersion | None:
    return current_version(DATASET)


def _row(year, values) -> dict | None:
    count, area, amount, premium, subsidy = values
    if not count:
        return None
    return {
        "year": year,
        "policies_count": int(count),
        "insured_area_ha": float(area or 0),
        "insured_amount": float(amount or 0),
        "premium_total": float(premium or 0),
        "subsidy_total": float(subsidy or 0),
    }


def latest_year(version_id: int) -> int | None:
    return db.session.scalar(select(func.max(InsuranceStat.year)).where(InsuranceStat.dataset_version_id == version_id))


def municipality_stat(version_id: int, ibge: int, crop_id: int | None, year: int) -> dict | None:
    crop_filter = InsuranceStat.crop_id.is_(None) if crop_id is None else InsuranceStat.crop_id == crop_id
    q = select(*SUM_COLS).where(
        InsuranceStat.dataset_version_id == version_id,
        InsuranceStat.municipality_ibge == ibge,
        crop_filter,
        InsuranceStat.year == year,
    )
    return _row(year, db.session.execute(q).one())


def uf_stat(version_id: int, uf: str, crop_id: int | None, year: int) -> dict | None:
    crop_filter = InsuranceStat.crop_id.is_(None) if crop_id is None else InsuranceStat.crop_id == crop_id
    q = (
        select(*SUM_COLS)
        .join(Municipality, Municipality.ibge_code == InsuranceStat.municipality_ibge)
        .where(
            InsuranceStat.dataset_version_id == version_id,
            Municipality.uf == uf,
            crop_filter,
            InsuranceStat.year == year,
        )
    )
    return _row(year, db.session.execute(q).one())


def years_series(version_id: int, ibge: int, crop_id: int | None) -> list[dict]:
    crop_filter = InsuranceStat.crop_id.is_(None) if crop_id is None else InsuranceStat.crop_id == crop_id
    q = (
        select(InsuranceStat.year, *SUM_COLS)
        .where(InsuranceStat.dataset_version_id == version_id, InsuranceStat.municipality_ibge == ibge, crop_filter)
        .group_by(InsuranceStat.year)
        .order_by(InsuranceStat.year)
    )
    return [r for r in (_row(row[0], row[1:]) for row in db.session.execute(q)) if r]
