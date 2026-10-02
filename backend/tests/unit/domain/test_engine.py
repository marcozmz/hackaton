"""Engine e regras: contexto → resultado, sem banco e sem rede."""
from datetime import date

from app.domain.context import (
    AgroContext,
    CropRef,
    MunicipalityRef,
    SoilRef,
    VarietyFacts,
    ZarcFacts,
    ZoneFacts,
)
from app.domain.engine import RecommendationEngine
from app.domain.narrative import Narrator
from app.domain.risk import ConfidenceLevel, RiskLevel, Status
from app.domain.zarc import combine

MUN = MunicipalityRef(3503208, "Araraquara", "SP", -21.79, -48.18)
CROP = CropRef(1, "milho", "Milho")
SOIL = SoilRef(2, "Meio-termo")


def zone(windows, soil=2, cycle=20, name="Milho 1ª Safra", climate=0):
    return ZoneFacts(name, soil, 2 if soil in (2, 13, 14) else 1, cycle, 1, climate, "Port.1", "2026/2027", windows)


def ctx(zones, soil=SOIL, as_of=date(2026, 10, 2), varieties=None, resolved_by="ibge_code", level="simple"):
    m = MunicipalityRef(MUN.ibge_code, MUN.name, MUN.uf, MUN.lat, MUN.lon, resolved_by)
    c = AgroContext(m, CROP, soil, as_of, level)
    c.facts["zarc"] = ZarcFacts(10, "Safra 2026/2027", tuple(zones))
    c.facts["varieties"] = varieties or VarietyFacts(11, ({"name": "BRS 1"}, {"name": "BRS 2"}))
    return c


ENGINE = RecommendationEngine()


def test_inside_window_low_risk_is_favorable():
    r = ENGINE.evaluate(ctx([zone({27: 20, 28: 20, 29: 20, 30: 30})]))
    assert r.status == Status.FAVORABLE
    assert r.risk_level == RiskLevel.LOW
    assert r.window["window_start"] == "2026-09-21"
    assert r.window["window_end"] == "2026-10-31"
    assert r.findings[0].code == "zarc_in_window"


def test_inside_window_40pct_is_high_attention():
    r = ENGINE.evaluate(ctx([zone({28: 40, 29: 40})]))
    assert r.status == Status.ATTENTION
    assert r.risk_level == RiskLevel.HIGH


def test_outside_window_is_unfavorable_with_next_window():
    r = ENGINE.evaluate(ctx([zone({33: 20, 34: 20})]))
    assert r.status == Status.UNFAVORABLE
    assert r.window["window_start"] == "2026-11-21"
    assert "wait_window" in r.actions


def test_no_zones_is_no_data_never_high_risk():
    r = ENGINE.evaluate(ctx([]))
    assert r.status == Status.NO_DATA
    assert r.risk_level == RiskLevel.UNKNOWN


def test_zone_without_windows_is_unfavorable():
    r = ENGINE.evaluate(ctx([zone({})]))
    assert r.status == Status.UNFAVORABLE
    assert r.window is None


def test_soil_unspecified_is_conservative_and_lowers_confidence():
    zones = [zone({27: 20, 28: 20, 29: 20}, soil=1), zone({28: 30, 29: 20, 30: 20}, soil=3)]
    r = ENGINE.evaluate(ctx(zones, soil=None))
    cw = combine(zones)
    assert set(cw.windows) == {28, 29}
    assert cw.windows[28] == 30  # maior risco entre os solos
    assert "soil_unspecified" in r.assumptions
    assert r.confidence_score == 0.8  # 1 − 0.15 (solo) − 0.05 (cultivar por UF)
    assert r.confidence_level == ConfidenceLevel.HIGH


def test_cycles_and_variants_are_union_with_lowest_risk():
    zones = [
        zone({28: 30}, cycle=20),
        zone({28: 20, 29: 20}, cycle=21),
        zone({3: 20}, name="Milho 2ª Safra"),
    ]
    cw = combine(zones)
    assert cw.windows == {28: 20, 29: 20, 3: 20}
    assert len(cw.options) == 3


def test_lower_risk_period_suggested():
    r = ENGINE.evaluate(ctx([zone({28: 40, 29: 20, 30: 20})]))
    codes = [f.code for f in r.findings]
    assert "zarc_lower_risk_period" in codes


def test_cultivar_unknown_adds_gap():
    r = ENGINE.evaluate(ctx([zone({28: 20})], varieties=VarietyFacts(11, ())))
    assert "cultivars" in r.gaps


def test_approximate_location_penalized():
    r = ENGINE.evaluate(ctx([zone({28: 20})], resolved_by="nearest_centroid"))
    assert "location_approximate" in r.assumptions


def test_narrator_produces_simple_text_for_every_finding():
    c = ctx([zone({28: 40, 29: 20})], soil=None)
    r = ENGINE.evaluate(c)
    n = Narrator().narrate(c, r)
    assert n.title.startswith("Dá para plantar milho")
    assert "1 de outubro" in n.summary
    assert all(reason["text"] and "—" not in reason["text"] for reason in n.reasons)
    assert all("—" not in a for a in n.actions)


def test_narrator_levels_differ():
    c1 = ctx([zone({28: 20})], level="simple")
    c2 = ctx([zone({28: 20})], level="technical")
    s1 = Narrator().narrate(c1, ENGINE.evaluate(c1)).summary
    s2 = Narrator().narrate(c2, ENGINE.evaluate(c2)).summary
    assert s1 != s2


def test_portaria_humanized():
    from app.domain.narrative.explainer import portaria_text

    assert portaria_text("Port.21_de_16-03-2026") == "Portaria nº 21, de 16/03/2026"
    assert portaria_text("algo estranho") == "algo estranho"
