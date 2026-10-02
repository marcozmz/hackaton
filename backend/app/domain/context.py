"""AgroContext: a "pergunta" do agricultor + fatos preenchidos pelos enrichers.

Nova dimensão (previsão, seguro, bioma...) = novo enricher que preenche
`facts["<nome>"]` + regras que leem esse fato. Nada mais muda.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class MunicipalityRef:
    ibge_code: int
    name: str
    uf: str
    lat: float
    lon: float
    resolved_by: str = "ibge_code"  # ibge_code | exact_name | fuzzy_name | cep | nearest_centroid


@dataclass(frozen=True)
class CropRef:
    id: int
    slug: str
    name: str
    matched_as: str | None = None


@dataclass(frozen=True)
class SoilRef:
    group_code: int  # 1 areia · 2 meio-termo · 3 barro
    name: str


@dataclass(frozen=True)
class ZoneFacts:
    """Uma zona ZARC (combinação cultura/variante × solo × ciclo × manejo × clima)."""

    zarc_crop_name: str
    soil_code: int
    soil_group: int
    cycle_code: int
    management_code: int
    climate_code: int
    portaria: str | None
    season_label: str | None
    windows: dict[int, int]  # decêndio → risco %
    management_level: int = 0  # NM1–NM4 (soja); 0 = não se aplica


@dataclass(frozen=True)
class ZarcFacts:
    dataset_version_id: int | None
    version_label: str | None
    zones: tuple[ZoneFacts, ...]
    is_current_season: bool = True


@dataclass(frozen=True)
class VarietyFacts:
    dataset_version_id: int | None
    items: tuple[dict, ...]  # {"name", "holder", "group", "zarc_crop_name"}
    granularity: str = "uf"  # uf | municipality


@dataclass(frozen=True)
class DayForecast:
    date: date
    t_min: float | None
    t_max: float | None
    precip_mm: float | None
    precip_prob: int | None
    wind_max_kmh: float | None = None
    et0_mm: float | None = None


@dataclass(frozen=True)
class ForecastFacts:
    run_id: int | None
    provider: str
    fetched_at: datetime
    valid_until: datetime
    days: tuple[DayForecast, ...]
    stale: bool = False  # provider fora: usando run antigo

    def upcoming(self, as_of: date, n: int) -> tuple[DayForecast, ...]:
        return tuple(d for d in self.days if d.date >= as_of)[:n]


@dataclass
class AgroContext:
    municipality: MunicipalityRef
    crop: CropRef
    soil: SoilRef | None
    as_of: date
    language_level: str = "simple"
    facts: dict[str, Any] = field(default_factory=dict)
    data_gaps: list[str] = field(default_factory=list)
