"""Open-Meteo: gratuito, sem chave (uso não comercial; dados CC BY 4.0 — citar a fonte).

Também há o FixtureWeatherProvider: lê uma resposta gravada e a "move" para hoje,
para demo/testes sem rede (risco "Open-Meteo instável na demo", files/14-mvp-scope.md).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from app.errors import UpstreamUnavailable
from app.providers.weather.base import DailyWeatherDTO, ForecastDTO

log = logging.getLogger(__name__)

DAILY_VARS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "et0_fao_evapotranspiration",
)


def parse_open_meteo(payload: dict, provider: str, lat: float, lon: float, shift_to: date | None = None) -> ForecastDTO:
    d = payload.get("daily") or {}
    times = d.get("time") or []
    if not times:
        raise UpstreamUnavailable("Previsão veio vazia.")
    offset = timedelta(0)
    if shift_to is not None:
        offset = shift_to - date.fromisoformat(times[0])

    def col(name, i):
        values = d.get(name) or []
        return values[i] if i < len(values) else None

    days = []
    for i, t in enumerate(times):
        prob = col("precipitation_probability_max", i)
        days.append(
            DailyWeatherDTO(
                date=date.fromisoformat(t) + offset,
                t_min=col("temperature_2m_min", i),
                t_max=col("temperature_2m_max", i),
                precip_mm=col("precipitation_sum", i),
                precip_prob=int(prob) if prob is not None else None,
                wind_max_kmh=col("wind_speed_10m_max", i),
                et0_mm=col("et0_fao_evapotranspiration", i),
            )
        )
    return ForecastDTO(provider, lat, lon, None, tuple(days), payload)


class OpenMeteoProvider:
    name = "open_meteo"
    URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout=(5, 15), retries: int = 1, session: requests.Session | None = None):
        self.timeout = timeout
        self.retries = retries
        self.http = session or requests.Session()

    def forecast(self, lat: float, lon: float, days: int = 10) -> ForecastDTO:
        params = {
            "latitude": round(lat, 2),
            "longitude": round(lon, 2),
            "daily": ",".join(DAILY_VARS),
            "timezone": "America/Sao_Paulo",
            "forecast_days": days,
        }
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.http.get(self.URL, params=params, timeout=self.timeout)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                if resp.status_code != 200:
                    raise UpstreamUnavailable(f"Open-Meteo respondeu {resp.status_code}.")
                return parse_open_meteo(resp.json(), self.name, lat, lon)
            except (requests.RequestException, ValueError) as e:
                last_error = e
                log.warning("open-meteo falhou (tentativa %s): %s", attempt + 1, type(e).__name__)
                time.sleep(0.5 * (attempt + 1))
        raise UpstreamUnavailable("Não consegui ver a previsão agora.") from last_error


class FixtureWeatherProvider:
    """Resposta gravada do Open-Meteo, com datas deslocadas para começar hoje."""

    name = "open_meteo_fixture"

    def __init__(self, path: Path):
        self.path = Path(path)

    def forecast(self, lat: float, lon: float, days: int = 10) -> ForecastDTO:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3))).date()
        dto = parse_open_meteo(payload, self.name, lat, lon, shift_to=today)
        return ForecastDTO(dto.provider, lat, lon, None, dto.days[:days], None)
