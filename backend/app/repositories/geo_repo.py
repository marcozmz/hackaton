"""Leitura das malhas estáticas por UF (cache em memória: ~0,3 MB por UF)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from flask import current_app


def _geo_dir() -> Path:
    return Path(current_app.config["GEO_DIR"])


@lru_cache(maxsize=32)
def _load(path: str, mtime: float) -> dict[int, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {int(f["properties"]["codarea"]): f["geometry"] for f in data["features"]}


def uf_geometries(uf: str) -> dict[int, dict] | None:
    """{ibge: geometria GeoJSON} da UF, ou None se a malha não foi baixada."""
    path = _geo_dir() / f"{uf.upper()}.geojson"
    if not path.exists():
        return None
    return _load(str(path), path.stat().st_mtime)


def geometry(ibge: int, uf: str) -> dict | None:
    geoms = uf_geometries(uf)
    return geoms.get(ibge) if geoms else None
