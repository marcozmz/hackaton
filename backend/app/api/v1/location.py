from flask import Blueprint, jsonify, request

from app.schemas.requests import AutocompleteQuery, LocationQuery
from app.services.location_service import LocationService


def register(bp: Blueprint) -> None:
    @bp.get("/location/resolve")
    def resolve_location():
        p = LocationQuery.model_validate(request.args.to_dict())
        res = LocationService().resolve(q=p.q, cep=p.cep, lat=p.lat, lon=p.lon, ibge=p.ibge)
        return jsonify(res.to_dict())

    @bp.get("/location/municipalities")
    def municipalities():
        p = AutocompleteQuery.model_validate(request.args.to_dict())
        return jsonify({"items": LocationService().autocomplete(p.q, p.uf, p.limit), "next_cursor": None})
