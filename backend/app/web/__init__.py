"""Páginas Jinja (frontend da equipe em ../templates). Chamam os MESMOS services da API,
nunca a API por HTTP (ADR-01). JS no navegador só usa a API para mapa e texto simplificado."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for
from pydantic import ValidationError

from app.errors import AppError
from app.repositories import catalog_repo
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
    return render_template("inicio.html", **_form_context())


@bp.get("/clima")
def clima():
    args = request.args.to_dict()
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


# Protótipos da equipe (funcionalidades futuras na visão: contas, perfil, chatbot).
@bp.get("/assistente")
def assistente():
    return render_template("chatbot.html")


@bp.get("/perfil")
def perfil():
    return render_template("perfil.html")


@bp.get("/login")
def login():
    return render_template("login.html")


@bp.get("/cadastro")
def cadastro():
    return render_template("cadastro.html")
