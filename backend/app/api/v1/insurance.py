from flask import Blueprint, jsonify, request

from app.schemas.requests import InsuranceQuery
from app.services.crop_service import CropService
from app.services.insurance_service import InsuranceService
from app.services.location_service import LocationService


def register(bp: Blueprint) -> None:
    @bp.get("/insurance/summary")
    def insurance_summary():
        p = InsuranceQuery.model_validate(request.args.to_dict())
        loc = LocationService().resolve(q=p.place, ibge=p.municipality)
        crop = CropService().resolve(p.crop, loc.municipality.uf)
        svc = InsuranceService()
        facts = svc.facts(loc.municipality, crop)
        return jsonify({"location": loc.to_dict(), "crop": {"slug": crop.slug, "name": crop.name},
                        **svc.present(facts, loc.municipality, None)})
