from flask import Blueprint, jsonify, request

from app.extensions import cache
from app.schemas.requests import CropQuery, VarietiesQuery
from app.services.crop_service import CropService
from app.services.location_service import LocationService


def register(bp: Blueprint) -> None:
    @bp.get("/crops")
    def search_crops():
        p = CropQuery.model_validate(request.args.to_dict())
        return jsonify(CropService().search(p.q or "", p.uf.upper() if p.uf else None))

    @bp.get("/crops/<slug>")
    def crop_detail(slug: str):
        return jsonify(CropService().detail(slug))

    @bp.get("/crops/<slug>/varieties")
    def crop_varieties(slug: str):
        p = VarietiesQuery.model_validate(request.args.to_dict())
        uf = p.uf.upper() if p.uf else LocationService().by_ibge(p.municipality).municipality.uf
        return jsonify(CropService().varieties(slug, uf))

    @bp.get("/soils")
    @cache.cached(timeout=3600)
    def soils():
        return jsonify({"items": CropService().soils(), "unknown_option": {"id": "nao_sei", "name": "Não sei"}})
