from datetime import date

from flask import Blueprint, jsonify, request

from app.schemas.requests import WeatherQuery
from app.services.location_service import LocationService
from app.services.weather_service import WeatherService


def register(bp: Blueprint) -> None:
    @bp.get("/weather/outlook")
    def weather_outlook():
        p = WeatherQuery.model_validate(request.args.to_dict())
        loc = LocationService().resolve(q=p.place, cep=p.cep, lat=p.lat, lon=p.lon, ibge=p.municipality)
        svc = WeatherService()
        fc = svc.forecast(loc.municipality)  # UpstreamUnavailable → 503 no envelope padrão
        return jsonify({"location": loc.to_dict(), **svc.present(fc, date.today(), p.level)})
