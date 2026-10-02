"""LocationService: texto | CEP | coordenada | código IBGE → município (+ confiança)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from app.domain.context import MunicipalityRef
from app.domain.text import normalize_name
from app.errors import LocationAmbiguous, LocationNotFound
from app.models import Municipality
from app.providers.registry import provider
from app.repositories import territory_repo

UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB",
    "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}
FUZZY_ACCEPT = 90
FUZZY_CANDIDATE = 80


@dataclass(frozen=True)
class LocationResult:
    municipality: MunicipalityRef
    confidence: str  # high | medium | low

    def to_dict(self) -> dict:
        m = self.municipality
        return {
            "ibge_code": m.ibge_code,
            "name": m.name,
            "uf": m.uf,
            "lat": m.lat,
            "lon": m.lon,
            "resolved_by": m.resolved_by,
            "confidence": self.confidence,
        }


def _ref(m: Municipality, resolved_by: str) -> MunicipalityRef:
    return MunicipalityRef(m.ibge_code, m.name, m.uf, m.centroid_lat, m.centroid_lon, resolved_by)


def _light_ref(row, resolved_by: str) -> MunicipalityRef:
    ibge, name, _norm, uf, lat, lon = row
    return MunicipalityRef(ibge, name, uf, lat, lon, resolved_by)


def _candidate(row) -> dict:
    return {"ibge_code": row[0], "name": row[1], "uf": row[3]}


def split_place(text: str) -> tuple[str, str | None]:
    """'Araraquara - SP' | 'araraquara/sp' | 'Araraquara SP' → ('araraquara', 'SP')."""
    raw = text.strip()
    m = re.match(r"^(.*?)[\s,/\-–]+([A-Za-z]{2})$", raw)
    if m and m.group(2).upper() in UFS:
        return normalize_name(m.group(1)), m.group(2).upper()
    return normalize_name(raw), None


def _haversine(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


class LocationService:
    def by_ibge(self, ibge_code: int) -> LocationResult:
        m = territory_repo.get(ibge_code)
        if m is None:
            raise LocationNotFound(details={"ibge_code": ibge_code})
        return LocationResult(_ref(m, "ibge_code"), "high")

    def by_text(self, text: str) -> LocationResult:
        if text.strip().isdigit() and len(text.strip()) == 7:
            return self.by_ibge(int(text.strip()))
        name, uf = split_place(text)
        if not name:
            raise LocationNotFound()
        exact = territory_repo.by_name(name, uf)
        if len(exact) == 1:
            return LocationResult(_ref(exact[0], "exact_name"), "high")
        if len(exact) > 1:
            raise LocationAmbiguous(
                details={"candidates": [{"ibge_code": m.ibge_code, "name": m.name, "uf": m.uf} for m in exact]}
            )
        rows = [r for r in territory_repo.all_light() if uf is None or r[3] == uf]
        matches = process.extract(name, [r[2] for r in rows], scorer=fuzz.ratio, limit=5)
        matches = [(rows[i], score) for _, score, i in matches if score >= FUZZY_CANDIDATE]
        if not matches:
            raise LocationNotFound(details={"query": text})
        best_row, best = matches[0]
        second = matches[1][1] if len(matches) > 1 else 0
        if best >= FUZZY_ACCEPT and best - second >= 5:
            return LocationResult(_light_ref(best_row, "fuzzy_name"), "medium")
        raise LocationAmbiguous(details={"candidates": [_candidate(r) for r, _ in matches]})

    def by_cep(self, cep: str) -> LocationResult:
        digits = re.sub(r"\D", "", cep)
        if len(digits) != 8:
            raise LocationNotFound("CEP inválido.", details={"cep": cep})
        res = provider("cep").lookup(digits)
        if res is None:
            raise LocationNotFound("CEP não encontrado.", details={"cep": cep})
        loc = self.by_ibge(res.ibge_code)
        return LocationResult(
            MunicipalityRef(**{**loc.municipality.__dict__, "resolved_by": "cep"}), "high"
        )

    def by_coordinates(self, lat: float, lon: float) -> LocationResult:
        rows = territory_repo.all_light()
        if not rows:
            raise LocationNotFound()
        best = min(rows, key=lambda r: _haversine(lat, lon, r[4], r[5]))
        # centroide mais próximo erra perto de divisas → confiança média, usuário confirma.
        return LocationResult(_light_ref(best, "nearest_centroid"), "medium")

    def resolve(self, *, q=None, cep=None, lat=None, lon=None, ibge=None) -> LocationResult:
        if ibge:
            return self.by_ibge(int(ibge))
        if cep:
            return self.by_cep(cep)
        if lat is not None and lon is not None:
            return self.by_coordinates(lat, lon)
        if q:
            return self.by_text(q)
        raise LocationNotFound("Informe um lugar (nome, CEP ou coordenadas).")

    def autocomplete(self, q: str, uf: str | None = None, limit: int = 20) -> list[dict]:
        rows = territory_repo.search(normalize_name(q), uf.upper() if uf else None, limit)
        return [{"ibge_code": m.ibge_code, "name": m.name, "uf": m.uf} for m in rows]
