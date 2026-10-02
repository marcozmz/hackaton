"""WeatherService: previsão do município com cache por run (TTL) e degradação graciosa.

Fluxo: run válido no banco? → usa · senão provider → persiste run · provider caiu →
último run com até 24 h (stale) · nada disso → UpstreamUnavailable.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from flask import current_app

from app.domain import weather
from app.domain.context import DayForecast, ForecastFacts, MunicipalityRef
from app.domain.narrative.narrator import Narrator, SafeDict, date_text
from app.errors import UpstreamUnavailable
from app.models import ForecastRun
from app.providers.registry import provider
from app.repositories import forecast_repo

log = logging.getLogger(__name__)
OUTLOOK_DAYS = 7


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _facts(run: ForecastRun, stale: bool) -> ForecastFacts:
    days = tuple(
        DayForecast(d.date, d.t_min, d.t_max, d.precip_mm, d.precip_prob, d.wind_max_kmh, d.et0_mm)
        for d in run.days
    )
    return ForecastFacts(run.id, run.provider, _utc(run.fetched_at), _utc(run.valid_until), days, stale)


class WeatherService:
    def enabled(self) -> bool:
        return provider("weather") is not None

    def forecast(self, m: MunicipalityRef) -> ForecastFacts:
        now = datetime.now(timezone.utc)
        last = forecast_repo.latest(m.ibge_code)
        if last and _utc(last.valid_until) > now:
            return _facts(last, stale=False)

        prov = provider("weather")
        if prov is None:
            raise UpstreamUnavailable("Previsão do tempo desativada.")
        try:
            dto = prov.forecast(m.lat, m.lon, current_app.config["FORECAST_DAYS"])
        except UpstreamUnavailable:
            max_age = timedelta(seconds=current_app.config["FORECAST_STALE_MAX_SECONDS"])
            if last and now - _utc(last.fetched_at) <= max_age:
                log.warning("previsão: usando run antigo #%s para %s", last.id, m.ibge_code)
                return _facts(last, stale=True)
            raise
        ttl = timedelta(seconds=current_app.config["FORECAST_TTL_SECONDS"])
        run = forecast_repo.save(m.ibge_code, dto, now, now + ttl)
        return _facts(run, stale=False)

    # --- apresentação -----------------------------------------------------
    def present(self, fc: ForecastFacts, as_of: date, level: str = "simple") -> dict:
        msgs = Narrator().m
        days = fc.upcoming(as_of, OUTLOOK_DAYS)
        rainiest = max(days, key=lambda d: d.precip_mm or 0.0, default=None)
        if rainiest and (rainiest.precip_mm or 0) >= 1:
            highlight = msgs["weather_highlight"]["rainiest"].format(
                day=weather.weekday(rainiest), mm=round(rainiest.precip_mm)
            )
        else:
            highlight = msgs["weather_highlight"]["none"]
        tpl = msgs["weather_summary"].get(level) or msgs["weather_summary"]["simple"]
        summary = tpl.format_map(
            SafeDict(
                n_days=len(days),
                mm_total=round(weather.total_rain(days)),
                t_max_max=round(max((d.t_max for d in days if d.t_max is not None), default=0)),
                t_min_min=round(min((d.t_min for d in days if d.t_min is not None), default=0)),
                highlight=highlight,
            )
        )
        return {
            "status": "degraded" if fc.stale else "ok",
            "summary": summary,
            "days": [
                {
                    "date": d.date.isoformat(),
                    "weekday": weather.weekday(d),
                    "label": date_text(d.date.isoformat()),
                    "condition": weather.condition(d),
                    "condition_label": msgs["weather_conditions"][weather.condition(d)],
                    "flags": [msgs["weather_flags"][f] for f in weather.temperature_flags(d)],
                    "t_min": d.t_min,
                    "t_max": d.t_max,
                    "precip_mm": d.precip_mm,
                    "precip_prob": d.precip_prob,
                }
                for d in days
            ],
            "fetched_at": fc.fetched_at.isoformat(timespec="seconds"),
            "valid_until": fc.valid_until.isoformat(timespec="seconds"),
            "source_id": "open_meteo",
        }

    def unavailable(self, reason: str = "unavailable") -> dict:
        return {"status": reason, "days": [], "summary": None, "source_id": "open_meteo"}
