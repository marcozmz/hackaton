"""IA para simplificar: só reescreve, guard valida, template é sempre o plano B."""
import pytest

from app.errors import UpstreamUnavailable
from app.providers.llm.base import LLMResult
from tests.conftest import ARARAQUARA

PARAMS = {"municipality": ARARAQUARA, "crop": "milho", "soil": "2", "date": "2026-10-02"}


class FakeLLM:
    name, model = "fake", "fake-1"

    def __init__(self, text="Agora é uma boa hora para plantar milho, até 31 de outubro.", down=False):
        self.text, self.down, self.calls, self.last_user = text, down, 0, None

    def complete(self, *, system, user, max_tokens, timeout):
        self.calls += 1
        self.last_user = user
        if self.down:
            raise UpstreamUnavailable("fora")
        return LLMResult(self.text, self.model, 10, 100, 30)


@pytest.fixture()
def llm(app):
    fake = FakeLLM()
    app.extensions["providers"]["llm"] = fake
    return fake


def simple(client):
    return client.get("/api/v1/recommendations/planting/simple", query_string=PARAMS).get_json()


def test_without_llm_uses_template(client):
    body = simple(client)
    assert body["generated_by"] == "template" and body["fallback_reason"] == "ia_desligada"
    assert body["text"].startswith("Bom momento para plantar milho")


def test_llm_text_used_when_guard_passes(client, llm):
    body = simple(client)
    assert body["generated_by"] == "llm" and body["text"] == llm.text and body["model"] == "fake-1"


def test_guard_rejects_invented_facts(client, llm):
    llm.text = "Plante até 15 de maio, a chance de perda é de 3%."
    body = simple(client)
    assert body["generated_by"] == "template" and body["fallback_reason"] == "guard_reprovou"
    assert body["guard_problems"]


def test_llm_down_falls_back(client, llm):
    llm.down = True
    body = simple(client)
    assert body["generated_by"] == "template" and body["fallback_reason"] == "ia_indisponivel"


def test_context_sent_has_no_ids_or_coordinates(client, llm):
    simple(client)
    sent = llm.last_user
    assert "Araraquara/SP" in sent
    assert "-21.78" not in sent and "-48.17" not in sent and str(ARARAQUARA) not in sent


def test_recommendation_itself_never_calls_llm(client, llm):
    client.get("/api/v1/recommendations/planting", query_string=PARAMS)
    assert llm.calls == 0
