from flask import Blueprint, jsonify, request

from app.schemas.requests import PlantingQuery
from app.services.recommendation_service import RecommendationService


def register(bp: Blueprint) -> None:
    @bp.get("/recommendations/planting")
    def planting():
        p = PlantingQuery.model_validate(request.args.to_dict())
        out = RecommendationService().planting_advice(
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
        return jsonify(out)
