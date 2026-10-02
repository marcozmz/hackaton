"""Páginas Jinja (frontend da equipe em ../templates). Chamam os MESMOS services da API,
nunca a API por HTTP (ADR-01). JS no navegador só usa a API para mapa e texto simplificado."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, redirect, render_template, request, session, url_for
from pydantic import ValidationError

from app.errors import AppError
from app.repositories import catalog_repo
from app.schemas.requests import PlantingQuery
from app.security.auth import csrf_token, current_user
from app.services.account_service import AccountService
from app.services.crop_service import CropService
from app.services.recommendation_service import RecommendationService
from app.web.share import recommendation_text, share_link
from app.web.view_model import clima_view

bp = Blueprint("web", __name__)


def _form_context(**extra) -> dict:
    return {
        "crops": catalog_repo.list_crops(),
        "soils": CropService().soils(),
        "form": request.args,
        **extra,
    }


LAST = "ultima_consulta"  # última consulta (município, cultura, terra) na sessão — sem dado pessoal


def _defaults() -> dict:
    """Consulta padrão: a última feita nesta sessão; senão a roça cadastrada; senão nada."""
    last = session.get(LAST)
    if last:
        return dict(last)
    user = current_user()
    if user and user.farm:
        farm = AccountService().farm_view(user)
        crop = farm["crops"][0] if farm["crops"] else None
        return {"municipality": farm["municipality"]["ibge_code"], "place": farm["place"],
                "crop": crop["slug"] if crop else "", "crop_name": crop["name"] if crop else "",
                "soil": str(farm["soil_group"] or "")}
    return {}


@bp.get("/")
def inicio():
    args = request.args
    if not args.get("nova") and args.get("crop") and (args.get("place") or args.get("lat")):
        return redirect(url_for("web.clima", **args))
    d = _defaults()
    # Já existe consulta (ou roça cadastrada): volta direto para o resultado.
    if not args.get("nova") and not args.get("conta_excluida") and d.get("municipality") and d.get("crop"):
        return redirect(url_for("web.clima"))
    form = args if args.get("place") or args.get("crop") else {
        "place": d.get("place", ""), "crop": d.get("crop_name", ""), "soil": d.get("soil", "")}
    return render_template("inicio.html", **_form_context(form=form, excluida=args.get("conta_excluida")))


@bp.get("/clima")
def clima():
    args = request.args.to_dict()
    user = current_user()
    d = _defaults()
    if not (args.get("place") or args.get("municipality") or args.get("lat")):
        if not d.get("municipality"):
            return redirect(url_for("web.inicio", nova=1))
        args["municipality"] = str(d["municipality"])
        args.setdefault("soil", d.get("soil", ""))
    if not args.get("crop") and d.get("crop"):
        args["crop"] = d["crop"]
    if user and "level" not in args:
        args["level"] = user.language_level
    try:
        p = PlantingQuery.model_validate(args)
        rec = RecommendationService().planting_advice(
            municipality=p.municipality, place=p.place, lat=p.lat, lon=p.lon,
            crop=p.crop, soil=p.soil, as_of=p.as_of, level=p.level,
        )
    except ValidationError:
        return render_template("inicio.html", **_form_context(error="Diga onde você está e o que quer plantar.")), 422
    except AppError as e:
        candidates = e.details.get("candidates") if isinstance(e.details, dict) else None
        return render_template("inicio.html", **_form_context(error=e.message, candidates=candidates, code=e.code)), e.status
    loc = rec["location"]
    session[LAST] = {"municipality": loc["ibge_code"], "place": f'{loc["name"]} {loc["uf"]}',
                     "crop": rec["crop"]["slug"], "crop_name": rec["crop"]["name"],
                     "soil": str(rec["soil"]["id"]) if rec.get("soil") else ""}
    from app.services.what_to_plant_service import WhatToPlantService

    soil_group = rec["soil"]["id"] if rec.get("soil") else None
    others = [i for i in WhatToPlantService().rank(_muni(loc["ibge_code"]), soil_group)["items"]
              if i["status"] == "now" and i["crop"]["slug"] != rec["crop"]["slug"]][:4]
    url = url_for("web.clima", municipality=loc["ibge_code"], crop=rec["crop"]["slug"],
                  soil=session[LAST]["soil"], _external=True)
    return render_template("clima.html", rec=rec, v=clima_view(rec), crops=catalog_repo.list_crops(),
                           query=args, now=datetime.now(), others=others,
                           whatsapp=share_link(recommendation_text(rec), url))


def _muni(ibge: int):
    from app.services.location_service import LocationService

    return LocationService().by_ibge(ibge).municipality


@bp.get("/assistente")
def assistente():
    user = current_user()
    farm = AccountService().farm_view(user) if user else None
    return render_template("chatbot.html", farm=farm, season=_season_label())


def _season_label() -> str | None:
    from app.repositories import zarc_repo

    v = zarc_repo.current()
    return v.version_label if v else None


@bp.app_context_processor
def _inject_ui():
    """Usuário, token CSRF e preferências visuais disponíveis em todos os templates."""
    user = current_user()
    font = {"normal": "16px", "grande": "18px", "muito-grande": "21px"}.get(user.font_size if user else "", "16px")
    return {
        "current_user": user,
        "csrf_token": csrf_token,
        "ui_html_class": "dark" if user and user.theme == "dark" else "",
        "ui_html_style": f"font-size:{font}",
    }


from app.web import account  # noqa: E402,F401  (registra as rotas de conta no mesmo blueprint)
from app.web import planning  # noqa: E402,F401  (aba Planejamento)
from app.web import what_to_plant  # noqa: E402,F401  ('O que plantar agora?')
from app.web import pwa  # noqa: E402,F401  (offline / instalar no celular)
