from datetime import date

import pytest

from app.domain import decendio as dec


@pytest.mark.parametrize(
    "d, expected",
    [
        (date(2026, 1, 1), 1),
        (date(2026, 1, 10), 1),
        (date(2026, 1, 11), 2),
        (date(2026, 1, 31), 3),
        (date(2026, 9, 30), 27),
        (date(2026, 10, 2), 28),
        (date(2026, 12, 31), 36),
    ],
)
def test_from_date(d, expected):
    assert dec.from_date(d) == expected


def test_bounds_handles_month_end_and_leap_year():
    assert dec.bounds(6, 2028) == (date(2028, 2, 21), date(2028, 2, 29))
    assert dec.bounds(6, 2027) == (date(2027, 2, 21), date(2027, 2, 28))
    assert dec.bounds(28, 2026) == (date(2026, 10, 1), date(2026, 10, 10))


def test_bounds_rejects_invalid():
    with pytest.raises(ValueError):
        dec.bounds(37, 2026)


def test_segments_merge_contiguous():
    segs = dec.segments([27, 28, 29, 33])
    assert [s.decendios for s in segs] == [(27, 28, 29), (33,)]
    assert segs[0].label() == "21 de set a 20 de out"


def test_segments_wrap_year():
    segs = dec.segments([1, 2, 35, 36, 10])
    assert [s.decendios for s in segs] == [(35, 36, 1, 2), (10,)]
    assert segs[0].label() == "11 de dez a 20 de jan"


def test_segments_full_year():
    assert dec.segments(range(1, 37))[0].decendios == tuple(range(1, 37))


def test_segment_dates_current_and_future():
    seg = dec.Segment((27, 28, 29))
    assert seg.dates(date(2026, 10, 2)) == (date(2026, 9, 21), date(2026, 10, 20))
    # segmento já passou neste ano → próxima ocorrência
    assert seg.dates(date(2026, 11, 15)) == (date(2027, 9, 21), date(2027, 10, 20))


def test_segment_dates_wrapping():
    seg = dec.Segment((35, 36, 1, 2))
    assert seg.dates(date(2027, 1, 5)) == (date(2026, 12, 11), date(2027, 1, 20))
    assert seg.dates(date(2026, 10, 2)) == (date(2026, 12, 11), date(2027, 1, 20))


def test_distance_from():
    assert dec.Segment((30, 31)).distance_from(28) == 2
    assert dec.Segment((1, 2)).distance_from(35) == 2
