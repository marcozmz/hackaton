"""Contrato de LLM. A IA só REESCREVE contexto estruturado; nunca decide (files/08-ai.md)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, *, system: str, user: str, max_tokens: int, timeout: float) -> LLMResult:
        """Levanta app.errors.UpstreamUnavailable em falha/timeout/cota."""
        ...
