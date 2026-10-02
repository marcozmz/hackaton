"""Melhor dia, 'o que plantar agora', WhatsApp e offline (PWA)."""
from urllib.parse import unquote

from tests.conftest import ARARAQUARA
from tests.integration.test_accounts import csrf

Q = {"municipality": ARARAQUARA, "crop": "milho", "soil": "2"}


def test_best_day_in_recommendation(client, weather):
    weather.rain = [0, 0, 0, 2, 8, 6, 0, 0, 0, 0]  # a partir de hoje (fixture), dentro da janela do teste
    body = client.get("/api/v1/recommendations/planting", query_string={**Q, "date": "2026-10-02"}).get_json()
    bd = body["best_day"]
    assert bd["status"] == "ok" and bd["date"] == "2026-10-05"
    assert any("chuva nos 3 dias seguintes" in r for r in bd["reasons"])
    assert any("prefira" in a for a in body["actions"])
    assert any(w["code"] == "best_sowing_day" for w in body["explanation"]["why"])


def test_no_good_day_when_storms(client, weather):
    weather.rain = [60, 60, 60, 60, 60, 60, 60, 60, 60, 60]
    body = client.get("/api/v1/recommendations/planting", query_string={**Q, "date": "2026-10-02"}).get_json()
    assert body["best_day"]["status"] == "none"


def test_what_to_plant_api_and_page(client):
    r = client.get("/api/v1/recommendations/what-to-plant", query_string={"municipality": ARARAQUARA, "soil": "2"})
    body = r.get_json()
    slugs = [i["crop"]["slug"] for i in body["items"]]
    assert set(slugs) >= {"milho", "mandioca", "feijao"}
    statuses = {i["crop"]["slug"]: i["status"] for i in body["items"]}
    assert statuses["feijao"] in ("later", "soon", "now") and statuses["soja"] == "no_data"
    order = [i["status"] for i in body["items"]]
    rank = {"now": 0, "soon": 1, "later": 2, "no_data": 3}
    assert order == sorted(order, key=rank.get)
    html = client.get("/o-que-plantar", query_string={"municipality": ARARAQUARA, "soil": "2"}).get_data(as_text=True)
    assert "O que dá para plantar agora" in html and "Mandar no WhatsApp" in html


def test_home_dont_know_button_goes_to_what_to_plant(client):
    html = client.get("/consulta", query_string={"nova": 1}).get_data(as_text=True)
    assert 'formaction="/o-que-plantar"' in html and "Não sei o que plantar" in html
    r = client.get("/o-que-plantar", query_string={"place": "Araraquara SP", "crop": "", "soil": ""})
    assert r.status_code == 200


def test_whatsapp_share_has_source_and_no_personal_data(client):
    html = client.get("/clima", query_string={**Q, "date": "2026-10-02"}).get_data(as_text=True)
    start = html.index("https://wa.me/?text=")
    link = unquote(html[start:html.index('"', start)])
    assert "Milho em Araraquara-SP" in link and "Fonte: calendário oficial ZARC" in link
    assert "@" not in link


def test_chat_what_to_plant(client):
    token = csrf(client, "/assistente")
    r = client.post("/assistente/mensagem", json={"text": "O que eu posso plantar em Araraquara SP?"},
                    headers={"X-CSRF-Token": token}).get_json()
    assert r["intent"] == "what_to_plant" and r["card"]["type"] == "list" and "Araraquara" in r["text"]


def test_pwa_assets(client):
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["Service-Worker-Allowed"] == "/"
    body = sw.get_data(as_text=True)
    assert "/clima" in body and "/perfil" not in body  # dados da conta não vão para o cache
    m = client.get("/manifest.webmanifest").get_json()
    assert m["short_name"] == "Plant+Facil" and m["display"] == "standalone"
    assert client.get("/icon.svg").status_code == 200
    assert "Sem internet" in client.get("/offline.js").get_data(as_text=True)
    assert 'rel="manifest"' in client.get("/clima", query_string=Q).get_data(as_text=True)
