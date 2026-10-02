"""Contas reais: cadastro, login, CSRF, propriedade, preferências, LGPD e assistente."""
import re

import pytest

from app.extensions import db
from app.models import Farm, Planting, User
from tests.conftest import ARARAQUARA


def csrf(client, url="/cadastro"):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([^"]+)"', html) or re.search(r"const CSRF = '([^']+)'", html)
    return m.group(1)


def signup(client, email="maria@exemplo.com", password="segredo1", name="Maria"):
    token = csrf(client)
    return client.post("/cadastro", data={"fullName": name, "email": email, "password": password,
                                          "terms": "1", "csrf_token": token})


@pytest.fixture()
def logged(client):
    r = signup(client)
    assert r.status_code == 302
    return client


def api(client, url, body):
    token = csrf(client, "/perfil")
    return client.post(url, json=body, headers={"X-CSRF-Token": token})


def logout(client):
    client.post("/sair", data={"csrf_token": csrf(client, "/perfil")})


def test_signup_hashes_password_and_logs_in(client):
    r = signup(client)
    assert r.status_code == 302 and "/perfil" in r.headers["Location"]
    u = db.session.query(User).one()
    assert u.email == "maria@exemplo.com" and "segredo1" not in u.password_hash
    assert client.get("/perfil").status_code == 200


def test_signup_requires_consent_and_valid_data(client):
    token = csrf(client)
    base = {"fullName": "Ana", "email": "ana@x.com", "password": "123456", "csrf_token": token}
    r = client.post("/cadastro", data=base)  # sem consentimento
    assert r.status_code == 422 and "concorda" in r.get_data(as_text=True)
    assert client.post("/cadastro", data={**base, "terms": "1", "email": "nao-e-email"}).status_code == 422
    assert client.post("/cadastro", data={**base, "terms": "1", "password": "123"}).status_code == 422


def test_duplicate_email(client):
    signup(client)
    logout(client)
    r = signup(client)
    assert r.status_code == 422 and "Já existe" in r.get_data(as_text=True)


def test_post_without_csrf_is_rejected(client):
    r = client.post("/cadastro", data={"fullName": "X", "email": "x@x.com", "password": "123456", "terms": "1"})
    assert r.status_code == 400


def test_login_logout_and_wrong_password(client):
    signup(client)
    logout(client)
    assert client.get("/perfil").status_code == 302
    token = csrf(client, "/login")
    bad = client.post("/login", data={"email": "maria@exemplo.com", "password": "errada", "csrf_token": token})
    assert bad.status_code == 401 and "não conferem" in bad.get_data(as_text=True)
    ok = client.post("/login", data={"email": "MARIA@exemplo.com ", "password": "segredo1", "csrf_token": token})
    assert ok.status_code == 302
    assert client.get("/perfil").status_code == 200


def test_login_rejects_external_next(client):
    signup(client)
    logout(client)
    token = csrf(client, "/login")
    r = client.post("/login", data={"email": "maria@exemplo.com", "password": "segredo1", "next": "//evil.com",
                                    "csrf_token": token})
    assert r.headers["Location"].endswith("/perfil")


def test_save_farm_and_profile_shows_real_recommendations(logged):
    r = api(logged, "/perfil/propriedade", {"place": "Araraquara SP", "area_ha": "12,5", "soil_group": "2",
                                            "crops": ["milho", "mandioca"], "name": "Sítio Teste"})
    assert r.status_code == 200
    farm = r.get_json()["farm"]
    assert farm["municipality"]["ibge_code"] == ARARAQUARA and farm["area_ha"] == 12.5
    assert {c["slug"] for c in farm["crops"]} == {"milho", "mandioca"}
    html = logged.get("/perfil").get_data(as_text=True)
    assert "Minhas lavouras hoje" in html and "Araraquara - SP" in html and "Sítio Teste" in html
    assert "Maria de Souza" not in html and "Pronaf" not in html


def test_save_farm_ambiguous_place(logged):
    r = api(logged, "/perfil/propriedade", {"place": "Bom Jesus", "crops": []})
    assert r.status_code == 409 and len(r.get_json()["error"]["details"]["candidates"]) == 2


def test_clima_uses_saved_farm_when_no_params(logged):
    api(logged, "/perfil/propriedade", {"place": "Araraquara SP", "soil_group": "2", "crops": ["milho"]})
    html = logged.get("/clima?date=2026-10-02").get_data(as_text=True)
    assert "Araraquara - SP" in html and "milho" in html.lower()


def test_preferences_persist_and_apply(logged):
    body = {"theme": "dark", "font_size": "muito-grande", "language_level": "technical"}
    assert api(logged, "/perfil/preferencias", body).status_code == 200
    u = db.session.query(User).one()
    assert (u.theme, u.font_size, u.language_level) == ("dark", "muito-grande", "technical")
    html = logged.get("/").get_data(as_text=True)
    assert 'class="dark"' in html and "font-size:21px" in html


def test_export_and_delete_account_lgpd(logged):
    api(logged, "/perfil/propriedade", {"place": "Araraquara SP", "crops": ["milho"]})
    data = logged.get("/perfil/meus-dados").get_json()
    assert data["conta"]["email"] == "maria@exemplo.com" and data["propriedade"]["crops"][0]["slug"] == "milho"
    r = logged.post("/perfil/excluir", data={"csrf_token": csrf(logged, "/perfil")})
    assert r.status_code == 302
    assert db.session.query(User).count() == 0
    assert db.session.query(Farm).count() == 0 and db.session.query(Planting).count() == 0


# --- assistente ----------------------------------------------------------------
def ask(client, text, context=None):
    token = csrf(client, "/assistente")
    r = client.post("/assistente/mensagem", json={"text": text, "context": context or {}},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 200
    return r.get_json()


def test_chat_planting_with_place_in_question(client):
    r = ask(client, "Posso plantar milho em Araraquara SP?")
    assert r["intent"] == "planting" and r["card"]["type"] == "planting"
    assert r["card"]["place"] == "Araraquara - SP" and r["context"]["crop"] == "milho"


def test_chat_follow_up_keeps_context(client):
    first = ask(client, "Posso plantar milho em Araraquara SP?")
    r = ask(client, "e o aipim?", first["context"])
    assert r["card"]["crop"] == "Mandioca" and r["card"]["place"] == "Araraquara - SP"


def test_chat_asks_place_when_unknown(client):
    r = ask(client, "Quando plantar milho na minha região?")
    assert r.get("needs") == "place" and "município" in r["text"]


def test_chat_uses_logged_user_farm(logged):
    api(logged, "/perfil/propriedade", {"place": "Araraquara SP", "soil_group": "2", "crops": ["milho"]})
    r = ask(logged, "Quando plantar milho na minha região?")
    assert r["card"]["place"] == "Araraquara - SP" and r["card"]["soil"] != "Não informado (período mais seguro)"


def test_chat_weather_glossary_varieties_and_pests(client, weather):
    weather.rain = [0, 0, 60, 0, 0, 0, 0, 0, 0, 0]
    w = ask(client, "Vai chover em Araraquara SP?")
    assert w["intent"] == "weather" and "chuva forte" in w["text"].lower() and len(w["card"]["days"]) == 7
    g = ask(client, "O que é o ZARC?")
    assert g["intent"] == "glossary" and "calendário oficial" in g["text"]
    v = ask(client, "Quais sementes de milho em Araraquara SP?")
    assert v["intent"] == "varieties" and "BRS 1010" in v["text"]
    p = ask(client, "Como combater lagarta com veneno?")
    assert p["intent"] == "out_of_scope_pests" and "Emater" in p["text"]


def test_chat_requires_csrf_and_text(client):
    assert client.post("/assistente/mensagem", json={"text": "oi"}).status_code == 400
    token = csrf(client, "/assistente")
    r = client.post("/assistente/mensagem", json={"text": "  "}, headers={"X-CSRF-Token": token})
    assert r.status_code == 422
