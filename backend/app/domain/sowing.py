"""Otimização do dia de semeadura: dentro da janela oficial, qual o MELHOR dia nos próximos dias?

Combina (pontuação explicável, sem caixa-preta):
- risco do ZARC no decêndio do dia (20% > 30% > 40%; fora da janela = descartado);
- chuva no próprio dia (temporal = descartado; encharcado = penaliza; terra úmida = bônus);
- chuva nos 3 dias seguintes (umidade para germinar = bônus; seca = penaliza);
- temporal nos 3 dias seguintes (lava a semente) e calor extremo (penalizam).
Pesos em thresholds.py (provisórios, documentados). Puro: sem I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain import decendio as dec
from app.domain.context import DayForecast
from app.domain.engine import thresholds as th

BASE_BY_RISK = {20: 60, 30: 40, 40: 25}


@dataclass
class DayScore:
    date: date
    score: int | None  # None = descartado
    risk_pct: int | None
    reasons: list[tuple[str, dict]] = field(default_factory=list)  # (código, params) p/ o Narrator


def score_days(windows: dict[int, int], forecast: list[DayForecast], today: date,
               horizon: int = th.SOWING_HORIZON_DAYS) -> list[DayScore]:
    days = sorted((d for d in forecast if d.date >= today), key=lambda d: d.date)
    by_date = {d.date: d for d in days}
    out: list[DayScore] = []
    for d in days[:horizon]:
        risk = windows.get(dec.from_date(d.date))
        if risk is None:
            out.append(DayScore(d.date, None, None, [("out_of_window", {})]))
            continue
        rain = d.precip_mm or 0.0
        if rain >= th.HEAVY_RAIN_MM_DAY:
            out.append(DayScore(d.date, None, risk, [("storm_on_day", {"mm": round(rain)})]))
            continue
        score = BASE_BY_RISK.get(risk, 20)
        reasons: list[tuple[str, dict]] = [("zarc_risk", {"risk": risk})]
        nxt = [by_date[x.date] for x in days if 0 < (x.date - d.date).days <= 3]
        if len(nxt) < 2:
            score -= 15  # previsão não cobre os dias seguintes: menos certeza
            reasons.append(("short_forecast", {}))
        storms = [x for x in nxt if (x.precip_mm or 0) >= th.HEAVY_RAIN_MM_DAY]
        # temporal não conta como "chuva boa": pode lavar a semente
        after = round(sum(x.precip_mm or 0.0 for x in nxt if x not in storms), 1)
        if after >= th.SOWING_GOOD_AFTER_MM:
            score += 25
            reasons.append(("rain_after", {"mm": round(after)}))
        elif after >= th.SOWING_SOME_AFTER_MM:
            score += 10
            reasons.append(("some_rain_after", {"mm": round(after)}))
        elif len(nxt) >= 2:
            score -= 10
            reasons.append(("dry_after", {"mm": round(after)}))
        if th.LIGHT_RAIN_MM_DAY <= rain <= th.MODERATE_RAIN_MM_DAY:
            score += 5
            reasons.append(("moist_day", {"mm": round(rain)}))
        elif rain > th.MODERATE_RAIN_MM_DAY:
            score -= 10
            reasons.append(("soaked_day", {"mm": round(rain)}))
        if storms:
            first = storms[0]
            days_after = (first.date - d.date).days
            score -= 40 if days_after == 1 else 30
            reasons.append(("storm_next_day" if days_after == 1 else "storm_after",
                            {"mm": round(first.precip_mm), "days": days_after}))
        if d.t_max is not None and d.t_max >= th.HOT_DAY_C:
            score -= 10
            reasons.append(("hot_day", {"t": round(d.t_max)}))
        out.append(DayScore(d.date, score, risk, reasons))
    return out


def best_day(scores: list[DayScore]) -> DayScore | None:
    ok = [s for s in scores if s.score is not None and s.score >= th.SOWING_MIN_SCORE]
    # empate: o mais cedo (não adia o plantio sem motivo)
    return max(ok, key=lambda s: (s.score, -s.date.toordinal()), default=None)
