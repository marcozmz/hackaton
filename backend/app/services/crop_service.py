"""CropService: nomes regionais → cultura oficial. Ambiguidade é resposta válida."""
from __future__ import annotations

from rapidfuzz import fuzz, process

from app.domain.context import CropRef, SoilRef
from app.domain.text import normalize_name
from app.errors import CropAmbiguous, CropNotFound, SoilNotFound
from app.ingestion.catalog_seed import load_soil_groups
from app.models import Crop
from app.repositories import catalog_repo, zarc_repo

# 1 letra errada em palavra curta ≈ 80 (WRatio). Aceita só com folga clara sobre a 2ª cultura.
FUZZY_ACCEPT = 80
FUZZY_MARGIN = 10
FUZZY_CANDIDATE = 70

SOIL_WORDS = {
    1: {"1", "areia", "arenoso", "arenosa", "terra de areia", "leve"},
    2: {"2", "media", "medio", "meio termo", "mista", "textura media"},
    3: {"3", "argila", "argiloso", "argilosa", "barro", "barrenta", "pesada", "massape"},
}


def crop_summary(c: Crop) -> dict:
    return {"slug": c.slug, "name": c.official_name, "category": c.category}


class CropService:
    def search(self, q: str, uf: str | None = None) -> dict:
        """{"match": {...} | None, "candidates": [...]} — nunca chuta entre opções."""
        norm = normalize_name(q)
        if not norm:
            return {"match": None, "candidates": [crop_summary(c) for c in catalog_repo.list_crops()]}

        exact = catalog_repo.aliases_exact(norm, uf)
        crop_ids = sorted({a.crop_id for a in exact})
        if len(crop_ids) == 1:
            c = catalog_repo.crop_by_id(crop_ids[0])
            return {"match": {**crop_summary(c), "matched_as": q.strip(), "match_type": "exact"}, "candidates": []}
        if len(crop_ids) > 1:
            return {"match": None, "candidates": [crop_summary(catalog_repo.crop_by_id(i)) for i in crop_ids]}

        aliases = [a for a in catalog_repo.all_aliases() if a[2] in (None, uf)]
        found = process.extract(norm, [a[1] for a in aliases], scorer=fuzz.WRatio, limit=10)
        best_by_crop: dict[int, float] = {}
        for _, score, idx in found:
            cid = aliases[idx][0]
            best_by_crop[cid] = max(best_by_crop.get(cid, 0), score)
        ranked = sorted(((s, cid) for cid, s in best_by_crop.items() if s >= FUZZY_CANDIDATE), reverse=True)
        if not ranked:
            return {"match": None, "candidates": []}
        best, cid = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0
        if best >= FUZZY_ACCEPT and best - second >= FUZZY_MARGIN:
            c = catalog_repo.crop_by_id(cid)
            return {
                "match": {**crop_summary(c), "matched_as": q.strip(), "match_type": "approximate"},
                "candidates": [],
            }
        return {"match": None, "candidates": [crop_summary(catalog_repo.crop_by_id(i)) for _, i in ranked]}

    def resolve(self, q: str, uf: str | None = None) -> CropRef:
        c = catalog_repo.crop_by_slug(q.strip().lower())
        if c:
            return CropRef(c.id, c.slug, c.official_name, None)
        res = self.search(q, uf)
        if res["match"]:
            m = res["match"]
            c = catalog_repo.crop_by_slug(m["slug"])
            return CropRef(c.id, c.slug, c.official_name, m["matched_as"])
        if res["candidates"]:
            raise CropAmbiguous(details={"candidates": res["candidates"], "query": q})
        raise CropNotFound(details={"query": q})

    def detail(self, slug: str) -> dict:
        c = catalog_repo.crop_by_slug(slug)
        if c is None:
            raise CropNotFound(details={"slug": slug})
        aliases = catalog_repo.aliases_of(c.id)
        return {
            **crop_summary(c),
            "scientific_name": c.scientific_name,
            "other_names": sorted({a.alias for a in aliases if a.kind in ("common", "regional")}),
            "has_zoning": zarc_repo.has_crop_anywhere(c.id),
        }

    def varieties(self, slug: str, uf: str) -> dict:
        c = catalog_repo.crop_by_slug(slug)
        if c is None:
            raise CropNotFound(details={"slug": slug})
        version, items = catalog_repo.varieties_for(c.id, uf)
        return {
            "crop": crop_summary(c),
            "uf": uf,
            "granularity": "uf",
            "items": [{"name": i["name"], "holder": i["holder"], "groups": i["groups"]} for i in items],
            "version_id": version.id if version else None,
        }

    # --- solos -------------------------------------------------------------
    def soils(self) -> list[dict]:
        groups = load_soil_groups()
        technical = {}
        for s in catalog_repo.soils():
            technical.setdefault(s.group_code, []).append(s.name_technical)
        return [
            {
                "id": g["code"],
                "name": g["name_simple"],
                "description": g["description_simple"],
                "zarc_classes": technical.get(g["code"], []),
            }
            for g in groups
        ]

    def resolve_soil(self, value: str | int | None) -> SoilRef | None:
        if value in (None, "", "nao_sei", "não sei"):
            return None
        norm = normalize_name(str(value))
        if norm in ("nao sei", "0"):
            return None
        groups = {g["code"]: g for g in load_soil_groups()}
        for code, words in SOIL_WORDS.items():
            if norm in words:
                return SoilRef(code, groups[code]["name_simple"])
        raise SoilNotFound(details={"soil": value, "accepted": [1, 2, 3, "areia", "media", "argila", "nao_sei"]})
