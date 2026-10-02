"""Interpretação pura da previsão: número → condição semântica (o frontend decide ícone/cor)."""
from __future__ import annotations

from app.domain.context import DayForecast
from app.domain.engine import thresholds as th

WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def condition(day: DayForecast) -> str:
    """heavy_rain | moderate_rain | rain | light_rain | dry. Chuva tem prioridade sobre temperatura."""
    mm = day.precip_mm or 0.0
    if mm >= th.HEAVY_RAIN_MM_DAY:
        return "heavy_rain"
    if mm >= th.MODERATE_RAIN_MM_DAY:
        return "moderate_rain"
    if mm >= th.RAIN_MM_DAY:
        return "rain"
    if mm >= th.LIGHT_RAIN_MM_DAY:
        return "light_rain"
    return "dry"


def temperature_flags(day: DayForecast) -> list[str]:
    flags = []
    if day.t_max is not None and day.t_max >= th.HOT_DAY_C:
        flags.append("hot")
    if day.t_min is not None and day.t_min <= th.COLD_NIGHT_C:
        flags.append("cold")
    return flags


def weekday(day: DayForecast) -> str:
    return WEEKDAYS[day.date.weekday()]


def total_rain(days) -> float:
    return round(sum(d.precip_mm or 0.0 for d in days), 1)
