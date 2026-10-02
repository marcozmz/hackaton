"""Ollama local (gratuito, offline). Ex.: `ollama pull qwen2.5:3b` e LLM_PROVIDER=ollama."""
from __future__ import annotations

import time

import requests

from app.errors import UpstreamUnavailable
from app.providers.llm.base import LLMResult


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str = "qwen2.5:3b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, *, system: str, user: str, max_tokens: int, timeout: float) -> LLMResult:
        t0 = time.perf_counter()
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.3},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=(3, timeout),
            )
            resp.raise_for_status()
            text = resp.json()["message"]["content"].strip()
        except (requests.RequestException, KeyError, ValueError) as e:
            raise UpstreamUnavailable("IA local indisponível.") from e
        return LLMResult(text, self.model, int((time.perf_counter() - t0) * 1000))
