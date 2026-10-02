"""Decêndios: 36 períodos de ~10 dias por ano (1–10, 11–20, 21–fim de cada mês).

Decêndio n → mês (n-1)//3 + 1. Ex.: 28 = 1–10 de outubro.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]
MONTHS_FULL = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def from_date(d: date) -> int:
    part = 0 if d.day <= 10 else 1 if d.day <= 20 else 2
    return (d.month - 1) * 3 + part + 1


def bounds(decendio: int, year: int) -> tuple[date, date]:
    if not 1 <= decendio <= 36:
        raise ValueError(f"decêndio inválido: {decendio}")
    month = (decendio - 1) // 3 + 1
    part = (decendio - 1) % 3
    start_day = 1 + part * 10
    end_day = start_day + 9 if part < 2 else calendar.monthrange(year, month)[1]
    return date(year, month, start_day), date(year, month, end_day)


def next_decendio(n: int) -> int:
    return 1 if n == 36 else n + 1


@dataclass(frozen=True)
class Segment:
    """Sequência contígua de decêndios (pode virar o ano: 35, 36, 1, 2)."""

    decendios: tuple[int, ...]

    @property
    def first(self) -> int:
        return self.decendios[0]

    @property
    def last(self) -> int:
        return self.decendios[-1]

    def __contains__(self, d: int) -> bool:
        return d in self.decendios

    def label(self) -> str:
        s, _ = bounds(self.first, 2001)
        _, e = bounds(self.last, 2001)
        return f"{s.day} de {MONTHS[s.month - 1]} a {e.day} de {MONTHS[e.month - 1]}"

    def dates(self, as_of: date) -> tuple[date, date]:
        """Datas concretas da ocorrência deste segmento que contém `as_of` ou vem depois dele."""
        today = from_date(as_of)
        year = as_of.year
        if today in self:
            # recua até o primeiro decêndio do segmento (pode estar no ano anterior)
            idx = self.decendios.index(today)
            start_year = year - 1 if any(d > today for d in self.decendios[:idx]) else year
        else:
            start_year = year if self.first > today else year + 1
        start, _ = bounds(self.first, start_year)
        end_year = start_year + (1 if self.last < self.first else 0)
        _, end = bounds(self.last, end_year)
        return start, end

    def distance_from(self, d: int) -> int:
        """Quantos decêndios faltam (a partir de d) até o início deste segmento."""
        return (self.first - d) % 36


def segments(decendios: set[int] | list[int]) -> list[Segment]:
    """Funde decêndios em segmentos contíguos, tratando a virada do ano."""
    ds = sorted(set(decendios))
    if not ds:
        return []
    if len(ds) == 36:
        return [Segment(tuple(range(1, 37)))]
    runs: list[list[int]] = [[ds[0]]]
    for d in ds[1:]:
        if d == runs[-1][-1] + 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    # junta o último com o primeiro se atravessam 36 → 1
    if len(runs) > 1 and runs[0][0] == 1 and runs[-1][-1] == 36:
        runs[0] = runs.pop() + runs[0]
    return [Segment(tuple(r)) for r in runs]


def end_of_decendio(d: date) -> date:
    _, end = bounds(from_date(d), d.year)
    return end


def days_until(d: date, other: date) -> int:
    return (other - d) // timedelta(days=1)
