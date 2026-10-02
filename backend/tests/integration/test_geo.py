"""Mapa: ponto + limite do município e camada de risco ZARC por UF."""
from pathlib import Path

import pytest

from tests.conftest import ARARAQUARA, ARARAS

GEO_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "geo"


@pytest.fixture()
def geo(app):
    app.config["GEO_DIR"] = str(GEO_FIXTURES)


def layer(client, **params):
    return client.get("/api/v1/geo/layers/zarc-risk", query_string={"uf": "SP", "date": "2026-10-02", **params}).get_json()


def levels(body):
    return {f["properties"]["ibge_code"]: f["properties"]["level"] for f in body["features"]}


def test_municipality_point_and_boundary(client, geo):
    body = client.get(f"/api/v1/geo/municipalities/{ARARAQUARA}").get_json()
    kinds = [(f["properties"]["kind"], f["geometry"]["type"]) for f in body["features"]]
    assert kinds == [("centroid", "Point"), ("boundary", "Polygon")]
    assert body["boundary_status"] == "ok"


def test_municipality_without_boundary_file_still_has_point(client, app, tmp_path):
    app.config["GEO_DIR"] = str(tmp_path)
    body = client.get(f"/api/v1/geo/municipalities/{ARARAQUARA}").get_json()
    assert body["boundary_status"] == "unavailable" and len(body["features"]) == 1


def test_zarc_layer_levels_match_recommendation_logic(client, geo):
    body = layer(client, crop="milho", soil="2")
    lv = levels(body)
    assert lv[ARARAQUARA] == "low"  # decêndio 28, solo 2 → 20%
    assert lv[ARARAS] == "no_data"
    assert body["summary"]["low"] == 1
    assert {i["level"] for i in body["legend"]} == {"low", "medium", "high", "out_of_window", "no_data"}


def test_zarc_layer_soil_unspecified_is_conservative(client, geo):
    assert levels(layer(client, crop="milho"))[ARARAQUARA] == "medium"  # max(20, 30)


def test_zarc_layer_out_of_window(client, geo):
    assert levels(layer(client, crop="aipim"))[ARARAQUARA] == "out_of_window"


def test_zarc_layer_semantic_only_no_colors_no_raw_codes(client, geo):
    body = layer(client, crop="milho", soil="2")
    raw = str(body)
    assert "#" not in raw and "risk_pct" not in raw and "decendio" not in raw
    assert body["features"][0]["properties"]["label"]
