"""Voltar ao "Clima e Plantio" não pode pedir tudo de novo (logado ou não)."""
from tests.integration.test_accounts import api, signup
from tests.conftest import ARARAQUARA

Q = {"municipality": ARARAQUARA, "crop": "milho", "soil": "2", "date": "2026-10-02"}


def test_anonymous_clima_remembers_last_query(client):
    assert client.get("/clima", query_string=Q).status_code == 200
    r = client.get("/clima")  # botão "Clima e Plantio" da barra
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Araraquara - SP" in html and "milho" in html.lower()


def test_home_goes_straight_to_result_after_a_query(client):
    client.get("/clima", query_string=Q)
    r = client.get("/")
    assert r.status_code == 302 and r.headers["Location"].endswith("/clima")


def test_new_query_form_is_prefilled_and_not_redirected(client):
    client.get("/clima", query_string=Q)
    r = client.get("/", query_string={"nova": 1, "place": "Araraquara SP", "crop": "Milho"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'value="Araraquara SP"' in html and 'value="Milho"' in html


def test_crop_switch_keeps_place(client):
    client.get("/clima", query_string=Q)
    html = client.get("/clima", query_string={"crop": "mandioca"}).get_data(as_text=True)
    assert "Araraquara - SP" in html and "Mandioca" in html


def test_first_visit_without_state_shows_form(client):
    r = client.get("/clima")
    assert r.status_code == 302 and "nova=1" in r.headers["Location"]
    assert client.get("/").status_code == 200


def test_logged_user_with_farm_goes_to_result(client):
    signup(client)
    api(client, "/perfil/propriedade", {"place": "Araraquara SP", "soil_group": "2", "crops": ["milho"]})
    r = client.get("/")
    assert r.status_code == 302 and r.headers["Location"].endswith("/clima")
    html = client.get("/clima").get_data(as_text=True)
    assert "Araraquara - SP" in html


def test_saving_farm_replaces_last_query(client):
    signup(client)
    client.get("/clima", query_string={"municipality": 3509502, "crop": "milho"})  # Campinas
    api(client, "/perfil/propriedade", {"place": "Araraquara SP", "soil_group": "2", "crops": ["milho"]})
    assert "Araraquara - SP" in client.get("/clima").get_data(as_text=True)
