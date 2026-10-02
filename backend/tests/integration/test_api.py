"""Fluxo da visão §16: onde? → o quê? → solo? → analisar → resultado."""
from tests.conftest import ARARAQUARA

TODAY = "2026-10-02"  # decêndio 28


def get(client, url, **params):
    resp = client.get(url, query_string=params)
    return resp.status_code, resp.get_json()


def test_health(client):
    code, body = get(client, "/api/v1/health")
    assert code == 200 and body["zarc_loaded"] is True


# --- localização -------------------------------------------------------------
def test_location_by_name_with_uf(client):
    code, body = get(client, "/api/v1/location/resolve", q="araraquara - sp")
    assert code == 200
    assert body["ibge_code"] == ARARAQUARA and body["resolved_by"] == "exact_name"


def test_location_fuzzy(client):
    code, body = get(client, "/api/v1/location/resolve", q="Araraquar SP")
    assert code == 200 and body["ibge_code"] == ARARAQUARA and body["confidence"] == "medium"


def test_location_same_name_two_states_is_ambiguous(client):
    code, body = get(client, "/api/v1/location/resolve", q="Bom Jesus")
    assert code == 409 and body["error"]["code"] == "location_ambiguous"
    assert {c["uf"] for c in body["error"]["details"]["candidates"]} == {"RS", "PI"}
    code, body = get(client, "/api/v1/location/resolve", q="Bom Jesus/RS")
    assert code == 200 and body["uf"] == "RS"


def test_location_by_coordinates(client):
    code, body = get(client, "/api/v1/location/resolve", lat=-21.80, lon=-48.17)
    assert body["ibge_code"] == ARARAQUARA and body["resolved_by"] == "nearest_centroid"


def test_location_validation_error(client):
    code, body = get(client, "/api/v1/location/resolve")
    assert code == 422 and body["error"]["code"] == "validation_error"


def test_autocomplete(client):
    code, body = get(client, "/api/v1/location/municipalities", q="arar", uf="SP")
    assert {m["name"] for m in body["items"]} == {"Araraquara", "Araras"}


# --- culturas ----------------------------------------------------------------
def test_regional_alias_resolves(client):
    for term in ("aipim", "Macaxeira", "MANDIOCA"):
        code, body = get(client, "/api/v1/crops", q=term)
        assert body["match"]["slug"] == "mandioca", term


def test_misspelling_resolves_approximately(client):
    code, body = get(client, "/api/v1/crops", q="mandioka")
    assert body["match"]["slug"] == "mandioca"
    assert body["match"]["match_type"] == "approximate"


def test_common_typos(client):
    for term, slug in [("fejao", "feijao"), ("soija", "soja"), ("macacheira", "mandioca"), ("feijão de corda", "feijao-caupi")]:
        _, body = get(client, "/api/v1/crops", q=term)
        assert body["match"] and body["match"]["slug"] == slug, term


def test_unknown_crop(client):
    code, body = get(client, "/api/v1/crops", q="xyzwq")
    assert body == {"match": None, "candidates": []}


def test_soils(client):
    code, body = get(client, "/api/v1/soils")
    assert [s["id"] for s in body["items"]] == [1, 2, 3]


def test_varieties(client):
    code, body = get(client, "/api/v1/crops/milho/varieties", municipality=ARARAQUARA)
    assert body["uf"] == "SP" and body["items"][0]["name"] == "BRS 1010"


# --- recomendação ------------------------------------------------------------
def rec(client, **params):
    return get(client, "/api/v1/recommendations/planting", date=TODAY, **params)


def test_recommendation_favorable_with_varieties_and_sources(client):
    code, body = rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    assert code == 200
    assert body["status"] == "favorable" and body["risk_level"] == "low"
    assert body["recommended_window"]["start"] == "2026-09-21"
    assert body["recommended_window"]["end"] == "2026-10-31"
    assert body["varieties"]["items"][0]["name"] == "BRS 1010"
    assert {s["id"] for s in body["sources"]} == {"zarc_tabua_risco", "zarc_cultivares"}
    assert body["actions"] and body["reason"]
    assert "cultivar_by_uf" not in body["confidence"]["assumptions"]  # texto, não código
    assert body["forecast"]["status"] == "unavailable"


def test_recommendation_by_place_text_and_alias(client):
    code, body = rec(client, place="Araraquara SP", crop="aipim", soil="2")
    assert body["crop"]["slug"] == "mandioca" and body["crop"]["matched_as"] == "aipim"
    assert body["status"] == "unfavorable"  # janela de jan–fev já passou
    assert body["recommended_window"]["start"] == "2027-01-01"


def test_recommendation_soil_unspecified_is_conservative(client):
    code, body = rec(client, municipality=ARARAQUARA, crop="milho")
    # interseção dos solos 2 e 3 = {28, 29}; dec 28 → max(20, 30) = 30 → atenção
    assert body["status"] == "attention" and body["risk_level"] == "medium"
    assert body["recommended_window"]["label"] == "1 de out a 20 de out"
    assert body["confidence"]["level"] in ("high", "medium")
    assert body["confidence"]["score"] < 1


def test_recommendation_zone_without_window(client):
    code, body = rec(client, municipality=ARARAQUARA, crop="feijao", soil="2")
    assert body["status"] == "unfavorable" and body["recommended_window"] is None


def test_recommendation_no_zoning_is_no_data(client):
    code, body = rec(client, municipality=3509502, crop="milho")
    assert code == 200
    assert body["status"] == "no_data" and body["risk_level"] == "unknown"


def test_recommendation_ambiguous_or_unknown_crop(client):
    code, body = rec(client, municipality=ARARAQUARA, crop="xyzwq")
    assert code == 404 and body["error"]["code"] == "crop_not_found"


def test_recommendation_invalid_soil(client):
    code, body = rec(client, municipality=ARARAQUARA, crop="milho", soil="lua")
    assert code == 422


def test_recommendation_levels(client):
    _, simple = rec(client, municipality=ARARAQUARA, crop="milho", soil="2", level="simple")
    _, tech = rec(client, municipality=ARARAQUARA, crop="milho", soil="2", level="technical")
    assert simple["summary"] != tech["summary"]


def test_raw_zarc_codes_never_leak_by_default(client):
    _, body = rec(client, municipality=ARARAQUARA, crop="milho", soil="2")
    assert "debug" not in body
    assert "decendio" not in str(body["explanation"])


def test_sources(client):
    code, body = get(client, "/api/v1/sources")
    ids = {s["id"]: s for s in body["items"]}
    assert ids["zarc_tabua_risco"]["status"] == "loaded"
    assert ids["zarc_tabua_risco"]["license"].startswith("Creative Commons")
