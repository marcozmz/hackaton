"""Planejamento (calendário): dia → situação oficial + sugestões. Puro, sem I/O.

Níveis de um dia (a partir da janela ZARC combinada):
- ideal:     decêndio indicado com risco 20%
- attention: decêndio indicado com risco 30–40%
- prep:      fora da janela, mas a janela abre no decêndio seguinte → preparar a terra
- out:       fora do período indicado
- no_data:   município sem zoneamento para a cultura
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.domain import decendio as dec
from app.domain.context import DayForecast
from app.domain.engine import thresholds as th

LEVELS = ("ideal", "attention", "prep", "out", "no_data")


@dataclass
class DayCell:
    date: date
    in_month: bool
    decendio: int
    level: str
    risk_pct: int | None
    rain_mm: float | None = None  # só dentro do horizonte da previsão
    heavy_rain: bool = False
    is_today: bool = False
    is_selected: bool = False
    tasks: int = 0
    done: int = 0
    best: bool = False  # melhor dia para semear (otimização)


@dataclass
class Window:
    label: str
    start: date
    end: date
    is_current: bool
    risk_min: int


@dataclass
class Suggestion:
    code: str
    params: dict = field(default_factory=dict)


def classify(windows: dict[int, int], d: date, has_zarc: bool) -> tuple[str, int | None]:
    if not has_zarc:
        return "no_data", None
    n = dec.from_date(d)
    if n in windows:
        r = windows[n]
        return ("ideal" if r <= 20 else "attention"), r
    if dec.next_decendio(n) in windows:
        return "prep", None
    return "out", None


def month_grid(
    year: int,
    month: int,
    windows: dict[int, int],
    has_zarc: bool,
    forecast: dict[date, DayForecast],
    today: date,
    selected: date | None = None,
    task_counts: dict[date, tuple[int, int]] | None = None,
) -> list[list[DayCell]]:
    """Semanas de domingo a sábado cobrindo o mês (com dias vizinhos esmaecidos)."""
    task_counts = task_counts or {}
    first = date(year, month, 1)
    start = first - timedelta(days=(first.weekday() + 1) % 7)  # volta até domingo
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    end += timedelta(days=(5 - end.weekday()) % 7)  # avança até sábado
    weeks, week, d = [], [], start
    while d <= end:
        level, risk = classify(windows, d, has_zarc)
        fc = forecast.get(d)
        mm = fc.precip_mm if fc else None
        total, done = task_counts.get(d, (0, 0))
        week.append(DayCell(d, d.month == month, dec.from_date(d), level, risk, mm,
                            bool(mm is not None and mm >= th.HEAVY_RAIN_MM_DAY), d == today, d == selected,
                            total, done))
        if len(week) == 7:
            weeks.append(week)
            week = []
        d += timedelta(days=1)
    return weeks


def current_or_next_window(windows: dict[int, int], today: date) -> Window | None:
    segs = dec.segments(windows)
    if not segs:
        return None
    n = dec.from_date(today)
    seg = next((s for s in segs if n in s), None) or min(segs, key=lambda s: s.distance_from(n))
    start, end = seg.dates(today)
    return Window(seg.label(), start, end, n in seg, min(windows[x] for x in seg.decendios))


def day_suggestions(
    cell: DayCell,
    fc: DayForecast | None,
    window: Window | None,
    varieties: int,
) -> list[Suggestion]:
    out: list[Suggestion] = []
    heavy = fc is not None and (fc.precip_mm or 0) >= th.HEAVY_RAIN_MM_DAY
    if cell.level == "no_data":
        return [Suggestion("no_data")]
    if cell.level in ("ideal", "attention"):
        if heavy:
            out.append(Suggestion("avoid_sowing_heavy_rain", {"mm": round(fc.precip_mm)}))
        else:
            out.append(Suggestion("sow" if cell.level == "ideal" else "sow_attention", {"risk": cell.risk_pct}))
            if fc is not None and (fc.precip_mm or 0) >= th.RAIN_MM_DAY:
                out.append(Suggestion("rain_helps", {"mm": round(fc.precip_mm)}))
        if varieties:
            out.append(Suggestion("use_indicated_seed", {"n": varieties}))
    elif cell.level == "prep":
        out.append(Suggestion("prepare_soil", {"start": window.start.isoformat() if window else None}))
        if varieties:
            out.append(Suggestion("buy_indicated_seed", {"n": varieties}))
        if heavy:
            out.append(Suggestion("heavy_rain_day", {"mm": round(fc.precip_mm)}))
    else:
        out.append(Suggestion("out_of_window", {"label": window.label if window else None,
                                                "start": window.start.isoformat() if window else None}))
    return out
