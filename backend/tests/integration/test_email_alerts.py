"""Aviso diário por e-mail: opt-in no perfil, campos para o webhook do Make e disparo uma vez por dia."""
from datetime import datetime

import pytest

from app.extensions import db
from app.models import User
from app.services import alert_service
from app.services.alert_service import BRT, AlertService, run_daily_if_due
from tests.integration.test_accounts import api, logged  # noqa: F401  (fixture)

HOOK = "https://hook.example.test/abc"


class FakePost:
    def __init__(self):
        self.calls = []

    def __call__(self, url, json, timeout):
        self.calls.append((url, json))
        return type("R", (), {"raise_for_status": lambda self: None})()


@pytest.fixture()
def hook(app, monkeypatch):
    app.config["MAKE_WEBHOOK_URL"] = HOOK
    fake = FakePost()
    monkeypatch.setattr(alert_service.requests, "post", fake)
    return fake


def _farm(client):
    api(client, "/perfil/propriedade", {"place": "Araraquara SP", "soil_group": "2", "crops": ["milho"]})


def test_profile_hides_option_when_server_has_no_webhook(logged):  # noqa: F811
    html = logged.get("/perfil").get_data(as_text=True)
    assert "ainda não estão ligados" in html and 'id="alerts-toggle"' not in html


def test_opt_in_and_payload_fields(logged, hook):  # noqa: F811
    _farm(logged)
    assert 'id="alerts-toggle"' in logged.get("/perfil").get_data(as_text=True)
    assert api(logged, "/perfil/avisos/teste", {}).status_code == 400  # sem opt-in não envia
    assert api(logged, "/perfil/avisos", {"on": True}).get_json()["on"] is True
    assert api(logged, "/perfil/avisos/teste", {}).status_code == 200
    url, data = hook.calls[-1]
    assert url == HOOK
    assert data["nome"] == "Maria" and data["email"] == "maria@exemplo.com" and data["cultura"] == "Milho"
    assert isinstance(data["latitude"], float) and isinstance(data["longitude"], float)
    assert data["titulo"] and data["mensagem"]
    assert api(logged, "/perfil/avisos", {"on": False}).get_json()["on"] is False
    assert logged.get("/perfil/meus-dados").get_json()["conta"]["aviso_por_email_desde"] is None


def test_without_farm_test_send_explains(logged, hook):  # noqa: F811
    api(logged, "/perfil/avisos", {"on": True})
    r = api(logged, "/perfil/avisos/teste", {})
    assert r.status_code == 400 and "roça" in r.get_json()["error"]["message"] and not hook.calls


def test_daily_run_sends_once_and_only_in_the_morning(app, logged, hook, tmp_path):  # noqa: F811
    _farm(logged)
    api(logged, "/perfil/avisos", {"on": True})
    app.instance_path = str(tmp_path)
    assert run_daily_if_due(app, datetime(2026, 10, 3, 5, 59, tzinfo=BRT)) is None
    assert run_daily_if_due(app, datetime(2026, 10, 3, 6, 0, tzinfo=BRT)) == {"enviados": 1, "sem_roca": 0, "falhas": 0}
    assert run_daily_if_due(app, datetime(2026, 10, 3, 7, 0, tzinfo=BRT)) is None  # já mandou hoje
    assert run_daily_if_due(app, datetime(2026, 10, 4, 15, 0, tzinfo=BRT)) is None  # à tarde não
    assert len(hook.calls) == 1


def test_send_all_skips_users_without_opt_in(app, logged, hook):  # noqa: F811
    _farm(logged)
    with app.app_context():
        assert AlertService().send_all() == {"enviados": 0, "sem_roca": 0, "falhas": 0}
        assert db.session.scalar(db.select(User)).email_alerts_since is None
