from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CepResult:
    ibge_code: int
    city: str
    uf: str


class CepProvider(Protocol):
    name: str

    def lookup(self, cep: str) -> CepResult | None:
        """None = CEP inexistente. Levanta UpstreamUnavailable se o serviço falhar."""
        ...


class NullCepProvider:
    name = "none"

    def lookup(self, cep: str) -> CepResult | None:
        from app.errors import UpstreamUnavailable

        raise UpstreamUnavailable("Busca por CEP desativada.")
