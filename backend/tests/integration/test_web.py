"""Páginas Jinja (frontend da equipe) renderizadas com os services reais."""
from tests.conftest import ARARAQUARA


def page(client, url, **params):
    r = client.get(url, query_string=params)
    return r.status_code, r.get_data(as_text=True)


def test_inicio_form(client):
    code, html = page(client, "/consulta")
    assert code == 200 and 'action="/clima"' in html and "Milho" in html


def test_landing_is_home_and_uses_our_api(client):
    code, html = page(client, "/")
    assert code == 200 and "Saiba o que e quando plantar" in html
    assert "/api/v1/recommendations/by-month" in html and "/api/v1/location/resolve" in html
    assert "supabase.co" not in html and "sb_publishable" not in html and "pk.eyJ" not in html


def test_clima_renders_real_recommendation(client, weather):
    weather.rain = [0, 0, 62, 5, 5, 5, 5, 5, 5, 5]
    code, html = page(client, "/clima", municipality=ARARAQUARA, crop="milho", soil="2", date="2026-10-02")
    assert code == 200
    assert "Dá para plantar milho, mas com atenção" in html  # card (chuva forte → atenção)
    assert "Chuva forte prevista" in html  # aviso vindo da regra
    assert "BRS 1010" in html  # cultivar
    assert "ZARC – Tábua de Risco" in html  # fontes no rodapé
    assert 'id="mapa"' in html and 'data-uf="SP"' in html


def test_clima_without_mockup_claims(client):
    _, html = page(client, "/clima", municipality=ARARAQUARA, crop="milho", soil="2", date="2026-10-02")
    for invented in ("Garantida", "garantida", "Pulverizar", "capacidade de campo", "Sítio Boa Esperança"):
        assert invented not in html


def test_clima_ambiguous_place_back_to_form_with_options(client):
    code, html = page(client, "/clima", place="Bom Jesus", crop="milho")
    assert code == 409 and "Bom Jesus - RS" in html and "Bom Jesus - PI" in html


def test_clima_missing_fields(client):
    code, html = page(client, "/clima", place="Araraquara SP")  # lugar sem cultura e sem consulta anterior
    assert code == 422 and "Diga onde você está" in html


def test_public_pages_and_profile_requires_login(client):
    for url in ("/assistente", "/login", "/cadastro"):
        assert client.get(url).status_code == 200
    r = client.get("/perfil")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
