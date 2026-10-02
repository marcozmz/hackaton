"""Páginas Jinja (frontend da equipe em ../templates). Chamam os MESMOS services da API,
nunca a API por HTTP (ADR-01). JS no navegador só usa a API para mapa e texto simplificado."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for
from pydantic import ValidationError

from app.errors import AppError
from app.repositories import catalog_repo
from app.security.auth import csrf_token, current_user
from app.services.account_service import AccountService
from app.schemas.requests import PlantingQuery
from app.services.crop_service import CropService
from app.services.recommendation_service import RecommendationService
from app.web.view_model import clima_view

bp = Blueprint("web", __name__)


def _form_context(**extra) -> dict:
    return {
        "crops": catalog_repo.list_crops(),
        "soils": CropService().soils(),
        "form": request.args,
        **extra,
    }


@bp.get("/")
def inicio():
    if request.args.get("crop") and (request.args.get("place") or request.args.get("lat")):
        return redirect(url_for("web.clima", **request.args))
    user = current_user()
    farm = AccountService().farm_view(user) if user else None
    defaults = {}
    if farm and not request.args:
        defaults = {"place": farm["place"], "soil": str(farm["soil_group"] or ""),
                    "crop": farm["crops"][0]["name"] if farm["crops"] else ""}
    return render_template("inicio.html", **_form_context(form=defaults or request.args,
                                                          excluida=request.args.get("conta_excluida")))


@bp.get("/clima")
def clima():
    args = request.args.to_dict()
    user = current_user()
    if user and user.farm and not (args.get("place") or args.get("municipality") or args.get("lat")):
        # sem lugar na URL: usa a propriedade cadastrada
        args.setdefault("municipality", str(user.farm.municipality_ibge))
        args.setdefault("soil", str(user.farm.soil_group or ""))
        if not args.get("crop") and user.farm.plantings:
            args["crop"] = catalog_repo.crop_by_id(user.farm.plantings[0].crop_id).slug
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
    return render_template("clima.html", rec=rec, v=clima_view(rec), crops=catalog_repo.list_crops(),
                           query=args, now=datetime.now())


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
