"""Páginas Jinja (frontend da equipe) renderizadas com os services reais."""
from tests.conftest import ARARAQUARA


def page(client, url, **params):
    r = client.get(url, query_string=params)
    return r.status_code, r.get_data(as_text=True)


def test_inicio_form(client):
    code, html = page(client, "/")
    assert code == 200 and 'action="/clima"' in html and "Milho" in html


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
    code, html = page(client, "/clima")
    assert code == 422 and "Diga onde você está" in html


def test_team_prototype_pages(client):
    for url in ("/assistente", "/perfil", "/login", "/cadastro"):
        assert client.get(url).status_code == 200
