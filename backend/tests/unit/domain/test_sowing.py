"""Otimização do melhor dia de semeadura (pura, explicável)."""
from datetime import date, timedelta

from app.domain import sowing
from app.domain.context import DayForecast

D0 = date(2026, 10, 2)  # decêndio 28
WIN = {28: 20, 29: 20, 30: 40}


def fc(rains, t_max=28.0):
    return [DayForecast(D0 + timedelta(days=i), 18.0, t_max, mm, 60) for i, mm in enumerate(rains)]


def test_prefers_day_with_rain_after_and_no_storm():
    scores = sowing.score_days(WIN, fc([0, 0, 0, 2, 8, 6, 0, 0, 0, 0]), D0)
    best = sowing.best_day(scores)
    # dia 3: terra úmida no dia (2 mm) + 14 mm nos 3 dias seguintes vence o dia 2 (só chuva depois)
    assert best.date == D0 + timedelta(days=3)
    assert ("rain_after", {"mm": 14}) in best.reasons and ("moist_day", {"mm": 2}) in best.reasons


def test_storm_day_is_discarded_and_storm_after_penalized():
    scores = {s.date: s for s in sowing.score_days(WIN, fc([0, 0, 0, 60, 5, 5, 5, 0, 0, 0]), D0)}
    assert scores[D0 + timedelta(days=3)].score is None  # temporal no dia
    before = scores[D0 + timedelta(days=2)]
    assert any(c == "storm_next_day" for c, _ in before.reasons)
    best = sowing.best_day(list(scores.values()))
    assert best.date > D0 + timedelta(days=3)  # depois do temporal


def test_out_of_window_days_not_suggested():
    scores = sowing.score_days({35: 20}, fc([5] * 10), D0)
    assert all(s.score is None for s in scores)
    assert sowing.best_day(scores) is None


def test_lower_zarc_risk_wins_with_same_weather():
    scores = sowing.score_days({28: 40, 29: 20}, fc([3] * 10), date(2026, 10, 8))
    best = sowing.best_day(scores)
    assert best.risk_pct == 20


def test_extreme_heat_penalized():
    hot = sowing.score_days(WIN, fc([0, 5, 5, 5, 0], t_max=38.0), D0)[0]
    mild = sowing.score_days(WIN, fc([0, 5, 5, 5, 0], t_max=28.0), D0)[0]
    assert hot.score < mild.score and any(c == "hot_day" for c, _ in hot.reasons)
