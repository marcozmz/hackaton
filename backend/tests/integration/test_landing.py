"""Landing integrada: consulta por mês 100% ZARC (sem IA gerando dados)."""
from tests.conftest import ARARAQUARA


def test_by_month_api_statuses_from_zarc(client):
    r = client.get("/api/v1/recommendations/by-month", query_string={"municipality": ARARAQUARA, "month": 10})
    b = r.get_json()
    assert r.status_code == 200 and b["localizacao"] == "Araraquara - SP"
    by = {c["slug"]: c for c in b["culturas"]}
    # mini-ZARC do teste: milho solo 2 → 27..30 (20/20/30/40); solo 3 → 28/29; conservador sem solo = {28: 30, 29: 30}
    assert by["milho"]["status"] == "atencao"
    assert [x["risco_percentual"] for x in by["milho"]["riscos"]] == [30, 30, None]
    assert by["mandioca"]["status"] == "nao_recomendado" and by["soja"]["status"] == "sem_dado"
    assert "ZARC" in b["fonte"]


def test_by_month_with_soil_and_validation(client):
    b = client.get("/api/v1/recommendations/by-month",
                   query_string={"municipality": ARARAQUARA, "month": 10, "soil": "2"}).get_json()
    milho = next(c for c in b["culturas"] if c["slug"] == "milho")
    assert milho["status"] == "recomendado" and milho["melhor_dia_do_mes"] == "2026-10-01"
    assert client.get("/api/v1/recommendations/by-month", query_string={"municipality": ARARAQUARA}).status_code == 422


def test_landing_without_mapbox_token_still_works(client, app):
    app.config["MAPBOX_TOKEN"] = ""
    html = client.get("/").get_data(as_text=True)
    assert "Mapa indisponível neste computador" in html and "mapbox-gl.js" not in html


def test_landing_with_token_loads_map_but_never_hardcodes_it(client, app):
    app.config["MAPBOX_TOKEN"] = "pk.teste123"
    html = client.get("/").get_data(as_text=True)
    assert "mapbox-gl.js" in html and '"pk.teste123"' in html  # vem da config (.env), não do arquivo
