from flask import Blueprint, jsonify, request

from app.extensions import limiter
from app.schemas.requests import PlantingQuery
from app.services.recommendation_service import RecommendationService
from app.services.crop_service import CropService
from app.services.location_service import LocationService
from app.services.simplify_service import SimplifyService
from app.services.what_to_plant_service import WhatToPlantService, by_month


def register(bp: Blueprint) -> None:
    def _advice(p: PlantingQuery) -> dict:
        return RecommendationService().planting_advice(
            municipality=p.municipality,
            place=p.place,
            cep=p.cep,
            lat=p.lat,
            lon=p.lon,
            crop=p.crop,
            soil=p.soil,
            as_of=p.as_of,
            level=p.level,
            debug=p.debug,
        )

    @bp.get("/recommendations/planting")
    def planting():
        return jsonify(_advice(PlantingQuery.model_validate(request.args.to_dict())))

    @bp.get("/recommendations/what-to-plant")
    def what_to_plant():
        """'O que plantar agora?': todas as culturas ordenadas pela situação de hoje no município."""
        a = request.args
        loc = LocationService().resolve(q=a.get("place"), ibge=a.get("municipality"),
                                        lat=a.get("lat", type=float), lon=a.get("lon", type=float))
        soil = CropService().resolve_soil(a.get("soil"))
        return jsonify(WhatToPlantService().rank(loc.municipality, soil.group_code if soil else None))

    @bp.get("/recommendations/by-month")
    def recommendations_by_month():
        """Culturas para um mês (landing): status de cada uma pelo ZARC, risco por decêndio."""
        a = request.args
        month = a.get("month", type=int)
        if not month or not 1 <= month <= 12:
            return jsonify({"error": {"code": "validation_error", "message": "Informe o mês (1 a 12)."}}), 422
        loc = LocationService().resolve(q=a.get("place"), ibge=a.get("municipality"),
                                        lat=a.get("lat", type=float), lon=a.get("lon", type=float))
        soil = CropService().resolve_soil(a.get("soil"))
        return jsonify(by_month(loc.municipality, soil.group_code if soil else None, month))

    @bp.get("/recommendations/planting/simple")
    @limiter.limit("10 per minute")
    def planting_simple():
        """Texto reescrito por IA (sob demanda). Sem IA/falha → texto do template."""
        p = PlantingQuery.model_validate(request.args.to_dict())
        rec = _advice(p)
        return jsonify({"recommendation_id": rec["id"], **SimplifyService().simplify(rec, p.level)})
