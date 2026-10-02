"""Página 'O que plantar agora?'."""
from __future__ import annotations

from flask import redirect, render_template, request, url_for

from app.errors import AppError
from app.services.crop_service import CropService
from app.services.location_service import LocationService
from app.services.what_to_plant_service import WhatToPlantService
from app.web import _defaults, bp
from app.web.share import share_link


@bp.get("/o-que-plantar")
def o_que_plantar():
    a = request.args
    d = _defaults()
    try:
        if a.get("place") or a.get("municipality"):
            loc = LocationService().resolve(q=a.get("place"), ibge=a.get("municipality")).municipality
            soil_param = a.get("soil", "")
        elif d.get("municipality"):
            loc = LocationService().by_ibge(int(d["municipality"])).municipality
            soil_param = a.get("soil", d.get("soil", ""))
        else:
            return redirect(url_for("web.inicio", nova=1))
        soil = CropService().resolve_soil(soil_param)
    except AppError as e:
        from app.web import _form_context

        candidates = e.details.get("candidates") if isinstance(e.details, dict) else None
        return render_template("inicio.html", **_form_context(error=e.message, candidates=candidates)), e.status
    r = WhatToPlantService().rank(loc, soil.group_code if soil else None)
    url = url_for("web.o_que_plantar", municipality=loc.ibge_code, soil=soil_param, _external=True)
    return render_template("o_que_plantar.html", r=r, soil=soil, soil_param=soil_param,
                           whatsapp=share_link(f"🌱 {r['summary']} (calendário oficial ZARC/MAPA)", url))
