from datetime import date

from flask import Blueprint, jsonify, request

from app.schemas.requests import ZarcLayerQuery
from app.services.crop_service import CropService
from app.services.geo_service import GeoService
from app.services.location_service import LocationService


def register(bp: Blueprint) -> None:
    @bp.get("/geo/municipalities/<int:ibge>")
    def geo_municipality(ibge: int):
        loc = LocationService().by_ibge(ibge)
        resp = jsonify(GeoService().municipality(loc))
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    @bp.get("/geo/layers/zarc-risk")
    def geo_zarc_risk():
        p = ZarcLayerQuery.model_validate(request.args.to_dict())
        crops = CropService()
        crop = crops.resolve(p.crop, p.uf.upper())
        soil = crops.resolve_soil(p.soil)
        layer = GeoService().zarc_risk_layer(
            p.uf, crop.slug, soil.group_code if soil else None, p.as_of or date.today()
        )
        resp = jsonify(layer)
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    @bp.get("/geo/legend")
    def geo_legend():
        return jsonify({"items": GeoService().legend()})
