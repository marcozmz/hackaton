"""Aba Planejamento com dados reais (ZARC + previsão + atividades do usuário)."""
from app.extensions import db
from app.models import FarmTask
from tests.conftest import ARARAQUARA
from tests.integration.test_accounts import api, csrf, signup

BASE = {"municipality": ARARAQUARA, "crop": "milho", "soil": "2"}


def page(client, **params):
    r = client.get("/planejamento", query_string={**BASE, **params})
    return r.status_code, r.get_data(as_text=True)


def test_calendar_shows_real_zarc_month(client):
    code, html = page(client, mes="2026-10", dia="2026-10-02")
    assert code == 200
    assert "Outubro 2026" in html and "Plantio indicado (risco baixo)" in html
    assert "Sexta-feira, 2 de outubro" in html and "Semear milho" in html
    for fake in ("72%", "tensiômetro", "35 sacas", "Pronaf", "Talhão", "Fevereiro 2025"):
        assert fake not in html


def test_next_windows_and_month_navigation(client):
    _, html = page(client, mes="2026-10")
    assert "Próximas Janelas de Plantio" in html and "Aberta agora" in html
    assert "mes=2026-09" in html and "mes=2026-11" in html


def test_without_state_goes_to_form(client):
    r = client.get("/planejamento")
    assert r.status_code == 302 and "nova=1" in r.headers["Location"]


def test_uses_last_query_from_clima(client):
    client.get("/clima", query_string={**BASE, "date": "2026-10-02"})
    r = client.get("/planejamento")
    assert r.status_code == 200 and "Araraquara" in r.get_data(as_text=True)


def test_anonymous_cannot_add_tasks(client):
    _, html = page(client)
    assert "Entre na sua conta para anotar" in html
    assert client.post("/planejamento/atividades", json={"date": "2026-10-02", "title": "x"}).status_code == 302


def test_tasks_crud_and_ownership(client):
    signup(client)
    token = csrf(client, "/perfil")
    h = {"X-CSRF-Token": token}
    r = client.post("/planejamento/atividades", json={"date": "2026-10-05", "title": "Comprar semente", "crop": "milho"}, headers=h)
    assert r.status_code == 201
    tid = r.get_json()["id"]
    _, html = page(client, dia="2026-10-05")
    assert "Comprar semente" in html
    assert client.post(f"/planejamento/atividades/{tid}/feito", json={"done": True}, headers=h).get_json()["done"]
    assert client.post("/planejamento/atividades", json={"date": "x", "title": "a"}, headers=h).status_code == 422
    assert client.post("/planejamento/atividades", json={"date": "2026-10-05", "title": " "}, headers=h).status_code == 422
    # outro usuário não enxerga nem altera
    client.post("/sair", data={"csrf_token": token})
    signup(client, email="outro@exemplo.com")
    h2 = {"X-CSRF-Token": csrf(client, "/perfil")}
    assert client.post(f"/planejamento/atividades/{tid}/feito", json={"done": False}, headers=h2).status_code == 404
    assert client.post(f"/planejamento/atividades/{tid}/excluir", headers=h2).status_code == 404
    _, html = page(client, dia="2026-10-05")
    assert "Comprar semente" not in html


def test_tasks_exported_and_deleted_with_account(client):
    signup(client)
    h = {"X-CSRF-Token": csrf(client, "/perfil")}
    client.post("/planejamento/atividades", json={"date": "2026-10-05", "title": "Preparar a terra"}, headers=h)
    assert client.get("/perfil/meus-dados").get_json()["atividades"][0]["titulo"] == "Preparar a terra"
    client.post("/perfil/excluir", data={"csrf_token": csrf(client, "/perfil")})
    assert db.session.query(FarmTask).count() == 0


def test_nav_has_planning_tab_everywhere(client):
    signup(client)
    api(client, "/perfil/propriedade", {"place": "Araraquara SP", "soil_group": "2", "crops": ["milho"]})
    for url in ("/clima", "/assistente", "/perfil", "/planejamento"):
        assert "/planejamento" in client.get(url).get_data(as_text=True), url
