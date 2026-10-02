"""ViaCEP: CEP → município (com código IBGE). Gratuito, sem chave."""
from __future__ import annotations

import logging

import requests

from app.errors import UpstreamUnavailable
from app.providers.geocoding.base import CepResult

log = logging.getLogger(__name__)


class ViaCepProvider:
    name = "viacep"
    URL = "https://viacep.com.br/ws/{cep}/json/"

    def __init__(self, timeout=(3, 8), session: requests.Session | None = None):
        self.timeout = timeout
        self.http = session or requests.Session()

    def lookup(self, cep: str) -> CepResult | None:
        try:
            resp = self.http.get(self.URL.format(cep=cep), timeout=self.timeout)
        except requests.RequestException as e:
            log.warning("viacep indisponível: %s", type(e).__name__)
            raise UpstreamUnavailable("Não consegui consultar o CEP agora.") from e
        if resp.status_code == 400:
            return None
        if resp.status_code >= 500:
            raise UpstreamUnavailable("Não consegui consultar o CEP agora.")
        data = resp.json()
        if data.get("erro") or not data.get("ibge"):
            return None
        return CepResult(int(data["ibge"]), data.get("localidade", ""), data.get("uf", ""))
