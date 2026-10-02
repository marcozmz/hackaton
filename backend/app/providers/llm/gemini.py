"""Google Gemini (API do Google AI Studio, cota gratuita). Chave em LLM_API_KEY — nunca logar."""
from __future__ import annotations

import logging
import time

import requests

from app.errors import UpstreamUnavailable
from app.providers.llm.base import LLMResult

log = logging.getLogger(__name__)


class GeminiProvider:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str = "gemini-3.5-flash-lite", session: requests.Session | None = None):
        self._key = api_key
        self.model = model
        self.http = session or requests.Session()

    def _thinking(self) -> dict:
        # Gemini 2.x usa orçamento de tokens; 3.x usa nível.
        return {"thinkingBudget": 0} if self.model.startswith("gemini-2") else {"thinkingLevel": "minimal"}

    def complete(self, *, system: str, user: str, max_tokens: int, timeout: float) -> LLMResult:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
                "thinkingConfig": self._thinking(),  # raciocínio mínimo: resposta curta e rápida
            },
        }
        t0 = time.perf_counter()
        try:
            resp = self.http.post(
                self.URL.format(model=self.model),
                headers={"x-goog-api-key": self._key},
                json=body,
                timeout=(5, timeout),
            )
        except requests.RequestException as e:
            log.warning("gemini indisponível: %s", type(e).__name__)
            raise UpstreamUnavailable("IA indisponível.") from e
        latency = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            status = (resp.json().get("error") or {}).get("status", "") if resp.content else ""
            log.warning("gemini HTTP %s %s", resp.status_code, status)  # sem corpo: pode ecoar conteúdo
            raise UpstreamUnavailable("IA indisponível.")
        data = resp.json()
        try:
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
        except (KeyError, IndexError) as e:
            raise UpstreamUnavailable("IA não devolveu texto.") from e
        usage = data.get("usageMetadata", {})
        return LLMResult(text, self.model, latency, usage.get("promptTokenCount"), usage.get("candidatesTokenCount"))
