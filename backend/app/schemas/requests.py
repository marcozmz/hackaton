"""Validação de entrada (query strings). Tamanhos e faixas limitados (ver 09-security)."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Level = Literal["simple", "standard", "technical"]


class _Q(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, populate_by_name=True)


class LocationQuery(_Q):
    q: str | None = Field(None, max_length=80)
    cep: str | None = Field(None, max_length=10)
    lat: float | None = Field(None, ge=-35, le=6)
    lon: float | None = Field(None, ge=-75, le=-28)
    ibge: int | None = Field(None, ge=1_000_000, le=9_999_999)

    @model_validator(mode="after")
    def _one(self):
        if not (self.q or self.cep or self.ibge or (self.lat is not None and self.lon is not None)):
            raise ValueError("informe q, cep, ibge ou lat+lon")
        return self


class AutocompleteQuery(_Q):
    q: str = Field(..., min_length=1, max_length=80)
    uf: str | None = Field(None, min_length=2, max_length=2)
    limit: int = Field(20, ge=1, le=50)


class CropQuery(_Q):
    q: str | None = Field(None, max_length=80)
    uf: str | None = Field(None, min_length=2, max_length=2)


class VarietiesQuery(_Q):
    municipality: int | None = Field(None, ge=1_000_000, le=9_999_999)
    uf: str | None = Field(None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def _one(self):
        if not (self.municipality or self.uf):
            raise ValueError("informe municipality ou uf")
        return self


class WeatherQuery(_Q):
    municipality: int | None = Field(None, ge=1_000_000, le=9_999_999)
    place: str | None = Field(None, max_length=80)
    cep: str | None = Field(None, max_length=10)
    lat: float | None = Field(None, ge=-35, le=6)
    lon: float | None = Field(None, ge=-75, le=-28)
    level: Level = "simple"

    @model_validator(mode="after")
    def _where(self):
        if not (self.municipality or self.place or self.cep or (self.lat is not None and self.lon is not None)):
            raise ValueError("informe municipality, place, cep ou lat+lon")
        return self


class PlantingQuery(_Q):
    municipality: int | None = Field(None, ge=1_000_000, le=9_999_999)
    place: str | None = Field(None, max_length=80)
    cep: str | None = Field(None, max_length=10)
    lat: float | None = Field(None, ge=-35, le=6)
    lon: float | None = Field(None, ge=-75, le=-28)
    crop: str = Field(..., min_length=1, max_length=80)
    soil: str | None = Field(None, max_length=30)
    as_of: dt.date | None = Field(None, alias="date")
    level: Level = "simple"
    debug: bool = False

    @model_validator(mode="after")
    def _where(self):
        if not (self.municipality or self.place or self.cep or (self.lat is not None and self.lon is not None)):
            raise ValueError("informe municipality, place, cep ou lat+lon")
        return self
