from flask import Blueprint, jsonify, request

from app.extensions import limiter
from app.schemas.requests import PlantingQuery
from app.services.recommendation_service import RecommendationService
from app.services.simplify_service import SimplifyService


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

    @bp.get("/recommendations/planting/simple")
    @limiter.limit("10 per minute")
    def planting_simple():
        """Texto reescrito por IA (sob demanda). Sem IA/falha → texto do template."""
        p = PlantingQuery.model_validate(request.args.to_dict())
        rec = _advice(p)
        return jsonify({"recommendation_id": rec["id"], **SimplifyService().simplify(rec, p.level)})
