from datetime import date

from app.domain import planning
from app.domain.context import DayForecast

WIN = {28: 20, 29: 30, 30: 40}  # 1–31 de outubro


def test_classify_levels():
    assert planning.classify(WIN, date(2026, 10, 2), True) == ("ideal", 20)
    assert planning.classify(WIN, date(2026, 10, 15), True) == ("attention", 30)
    assert planning.classify(WIN, date(2026, 9, 25), True) == ("prep", None)  # janela abre no decêndio seguinte
    assert planning.classify(WIN, date(2026, 12, 1), True) == ("out", None)
    assert planning.classify({}, date(2026, 10, 2), False) == ("no_data", None)


def test_month_grid_starts_sunday_and_marks_rain_and_tasks():
    fc = {date(2026, 10, 5): DayForecast(date(2026, 10, 5), 15, 25, 62, 90)}
    weeks = planning.month_grid(2026, 10, WIN, True, fc, date(2026, 10, 2), date(2026, 10, 5),
                                {date(2026, 10, 5): (2, 1)})
    assert all(len(w) == 7 for w in weeks)
    assert weeks[0][0].date.weekday() == 6  # domingo
    cells = {c.date: c for w in weeks for c in w}
    assert cells[date(2026, 10, 5)].heavy_rain and cells[date(2026, 10, 5)].is_selected
    assert (cells[date(2026, 10, 5)].tasks, cells[date(2026, 10, 5)].done) == (2, 1)
    assert cells[date(2026, 10, 2)].is_today and not cells[date(2026, 9, 30)].in_month


def test_window_current_or_next():
    w = planning.current_or_next_window(WIN, date(2026, 10, 2))
    assert w.is_current and w.start == date(2026, 10, 1) and w.risk_min == 20
    w = planning.current_or_next_window(WIN, date(2026, 11, 15))
    assert not w.is_current and w.start == date(2027, 10, 1)


def test_suggestions_follow_rules():
    cell = planning.DayCell(date(2026, 10, 5), True, 28, "ideal", 20)
    heavy = DayForecast(date(2026, 10, 5), 15, 25, 62, 90)
    codes = [s.code for s in planning.day_suggestions(cell, heavy, None, 3)]
    assert codes[0] == "avoid_sowing_heavy_rain" and "sow" not in codes
    codes = [s.code for s in planning.day_suggestions(cell, None, None, 0)]
    assert codes == ["sow"]
    prep = planning.DayCell(date(2026, 9, 25), True, 27, "prep", None)
    w = planning.current_or_next_window(WIN, date(2026, 9, 25))
    s = planning.day_suggestions(prep, None, w, 5)
    assert [x.code for x in s] == ["prepare_soil", "buy_indicated_seed"] and s[0].params["start"] == "2026-10-01"
