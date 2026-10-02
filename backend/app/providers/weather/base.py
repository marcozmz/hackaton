"""Contrato de previsão. `ForecastDTO` é o NOSSO formato (°C, mm, km/h, datas locais, UTC nos instantes)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class DailyWeatherDTO:
    date: date
    t_min: float | None
    t_max: float | None
    precip_mm: float | None
    precip_prob: int | None
    wind_max_kmh: float | None
    et0_mm: float | None


@dataclass(frozen=True)
class ForecastDTO:
    provider: str
    lat: float
    lon: float
    issued_at: datetime | None
    days: tuple[DailyWeatherDTO, ...]
    raw: dict | None = None


class WeatherProvider(Protocol):
    name: str

    def forecast(self, lat: float, lon: float, days: int) -> ForecastDTO:
        """Levanta app.errors.UpstreamUnavailable se o serviço falhar."""
        ...
