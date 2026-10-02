"""Regras de previsão (desejável). Limiares em thresholds.py, rotulados provisional.

Previsão nunca cria janela de plantio: ela ajusta o "quando, dentro da janela" e avisa riscos.
"""
from __future__ import annotations

from app.domain import decendio as dec
from app.domain import weather
from app.domain.context import AgroContext, ForecastFacts
from app.domain.engine import thresholds as th
from app.domain.engine.finding import Evidence, Finding
from app.domain.risk import Severity
from app.domain.zarc import combine

SOURCE = "open_meteo"


def _fc(ctx: AgroContext) -> ForecastFacts | None:
    return ctx.facts.get("forecast")


def _ev(fc: ForecastFacts, data: dict) -> Evidence:
    return Evidence(SOURCE, None, {"forecast_run_id": fc.run_id, **data}, fc.valid_until)


def _in_window(ctx: AgroContext) -> bool:
    z = ctx.facts.get("zarc")
    return bool(z and z.zones) and dec.from_date(ctx.as_of) in combine(z.zones).windows


class ForecastAvailabilityRule:
    """Previsão esperada mas indisponível/antiga → reduz confiança (nunca muda o risco)."""

    id, version = "forecast_availability", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        return "forecast" in ctx.data_gaps or bool(_fc(ctx) and _fc(ctx).stale)

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        if "forecast" in ctx.data_gaps:
            return [
                Finding(
                    "forecast_unavailable", Severity.INFO, 0.4, Evidence(SOURCE), self.id, self.version,
                    actions=("check_forecast_later",),
                    confidence_penalty=th.CONFIDENCE_PENALTY["forecast_unavailable"],
                )
            ]
        fc = _fc(ctx)
        return [
            Finding(
                "forecast_stale", Severity.INFO, 0.3, _ev(fc, {"fetched_at": fc.fetched_at.isoformat()}),
                self.id, self.version,
                confidence_penalty=th.CONFIDENCE_PENALTY["forecast_stale"],
                gap="forecast_stale",
            )
        ]


class ForecastHeavyRainRule:
    id, version = "forecast_heavy_rain", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        return bool(_fc(ctx) and _fc(ctx).days)

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        fc = _fc(ctx)
        days = fc.upcoming(ctx.as_of, th.FORECAST_HORIZON_DAYS)
        worst = max(days, key=lambda d: d.precip_mm or 0.0, default=None)
        if worst is None or (worst.precip_mm or 0) < th.MODERATE_RAIN_MM_DAY:
            return []
        heavy = (worst.precip_mm or 0) >= th.HEAVY_RAIN_MM_DAY
        params = {
            "mm": round(worst.precip_mm),
            "day": weather.weekday(worst),
            "date": worst.date.isoformat(),
            "threshold": th.HEAVY_RAIN_MM_DAY if heavy else th.MODERATE_RAIN_MM_DAY,
        }
        return [
            Finding(
                "forecast_heavy_rain" if heavy else "forecast_moderate_rain",
                Severity.ATTENTION if heavy else Severity.INFO,
                0.9 if heavy else 0.6,
                _ev(fc, {"date": params["date"], "precip_mm": worst.precip_mm}),
                self.id, self.version, params=params,
                actions=("avoid_soil_work_before_rain",) if heavy else ("plan_around_rain",),
            )
        ]


class ForecastSowingMoistureRule:
    """Dentro da janela: tem chuva vindo para a semente germinar, ou vem um período seco?"""

    id, version = "forecast_dry_spell", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        return bool(_fc(ctx) and _fc(ctx).days) and _in_window(ctx)

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        fc = _fc(ctx)
        days = fc.upcoming(ctx.as_of, th.DRY_SPELL_DAYS)
        if len(days) < th.DRY_SPELL_DAYS:
            return []
        total = weather.total_rain(days)
        params = {"mm_total": round(total), "n_days": len(days)}
        if total < th.DRY_SPELL_MAX_MM:
            return [
                Finding(
                    "forecast_dry_spell", Severity.ATTENTION, 0.8, _ev(fc, {"precip_total_mm": total}),
                    self.id, self.version, params=params, actions=("wait_soil_moisture",),
                )
            ]
        if total >= th.GOOD_MOISTURE_MM:
            return [
                Finding(
                    "forecast_good_moisture", Severity.OK, 0.7, _ev(fc, {"precip_total_mm": total}),
                    self.id, self.version, params=params,
                )
            ]
        return []
