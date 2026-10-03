"""Previsão: regras, cache por run, degradação graciosa e endpoint."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.extensions import db
from app.models import ForecastRun
from tests.conftest import ARARAQUARA, DAY0

TODAY = "2026-10-02"


def rec(client, **params):
    resp = client.get("/api/v1/recommendations/planting", query_string={"date": TODAY, **params})
    return resp.get_json()


def codes(body):
    return [r["code"] for r in body["explanation"]["reasons"]]


def test_heavy_rain_raises_attention_inside_low_risk_window(client, weather):
    weather.rain = [0, 0, 62, 5, 5, 5, 5, 5, 5, 5]
    body = rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    assert "forecast_heavy_rain" in codes(body)
    assert body["status"] == "attention" and body["risk_level"] == "medium"
    assert any("chuva forte" in a for a in body["actions"])


def test_moderate_rain_is_informative_only(client, weather):
    weather.rain = [0, 35, 5, 5, 5, 5, 5, 5, 5, 5]
    body = rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    assert "forecast_moderate_rain" in codes(body)
    assert body["status"] == "favorable"


def test_dry_spell_in_window(client, weather):
    weather.rain = [0, 0, 1, 0, 2, 0, 0, 0, 0, 0]
    body = rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    assert "forecast_dry_spell" in codes(body)
    assert body["status"] == "attention"


def test_good_moisture_in_window(client, weather):
    weather.rain = [5, 8, 6, 4, 3, 2, 1, 0, 0, 0]
    body = rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    assert "forecast_good_moisture" in codes(body)
    assert body["status"] == "favorable"


def test_dry_spell_ignored_outside_window(client, weather):
    weather.rain = [0] * 10
    body = rec(client, municipality=ARARAQUARA, crop="mandioca", soil="2")
    assert body["status"] == "unfavorable"
    assert "forecast_dry_spell" not in codes(body)


def test_provider_down_degrades_gracefully(client, weather):
    weather.down = True
    body = rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    assert body["status"] == "favorable"  # ZARC continua decidindo
    assert body["forecast"]["status"] == "unavailable"
    assert "Previsão do tempo indisponível." in body["confidence"]["gaps"]
    assert body["confidence"]["score"] <= 0.8


def test_forecast_run_is_cached_and_persisted(client, weather):
    rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    rec(client, municipality=ARARAQUARA, crop="feijao", soil="2")
    assert weather.calls == 1
    assert db.session.scalar(select(func.count()).select_from(ForecastRun)) == 1


def test_stale_run_used_when_provider_down(client, weather):
    rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    run = db.session.scalar(select(ForecastRun))
    run.valid_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    weather.down = True
    body = rec(client, municipality=ARARAQUARA, crop="milho", soil="3")
    assert body["forecast"]["status"] == "degraded"
    assert "Previsão do tempo desatualizada." in body["confidence"]["gaps"]


def test_outlook_endpoint(client, weather):
    off = max(0, (date.today() - DAY0).days)  # a rota mostra a partir de hoje; a previsão falsa começa em DAY0
    weather.rain = ([0] * off + [0, 12, 55] + [0] * 10)[:10]
    resp = client.get("/api/v1/weather/outlook", query_string={"place": "Araraquara SP"})
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["location"]["ibge_code"] == ARARAQUARA
    conditions = [d["condition"] for d in body["days"]]
    assert conditions[:3] == ["dry", "rain", "heavy_rain"]
    assert "55 mm" in body["summary"]


def test_outlook_endpoint_provider_down_is_503(client, weather):
    weather.down = True
    resp = client.get("/api/v1/weather/outlook", query_string={"municipality": ARARAQUARA})
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "upstream_unavailable"


def test_sources_lists_open_meteo_as_live(client):
    items = {s["id"]: s for s in client.get("/api/v1/sources").get_json()["items"]}
    assert items["open_meteo_forecast"]["status"] == "live"
