"""Rotas de conta: cadastro, login, perfil (propriedade, preferências, LGPD) e chat."""
from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for

from app.errors import AppError
from app.extensions import limiter
from app.repositories import catalog_repo
from app.security.auth import (
    check_csrf,
    current_user,
    login_required,
    login_user,
    logout_user,
    safe_next,
)
from app.services.account_service import AccountService
from app.services.chat_service import ChatService
from app.services.crop_service import CropService
from app.services.recommendation_service import RecommendationService
from app.web import bp


@bp.route("/cadastro", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def cadastro():
    if request.method == "GET":
        return render_template("cadastro.html", form={})
    check_csrf()
    f = request.form
    try:
        user = AccountService().register(f.get("fullName", ""), f.get("email", ""), f.get("password", ""),
                                         bool(f.get("terms")))
    except AppError as e:
        return render_template("cadastro.html", error=e.message, form=f), e.status
    login_user(user, remember=True)
    return redirect(url_for("web.perfil", novo=1))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "GET":
        if current_user():
            return redirect(url_for("web.perfil"))
        return render_template("login.html", form={}, next=request.args.get("next"))
    check_csrf()
    f = request.form
    try:
        user = AccountService().authenticate(f.get("email", ""), f.get("password", ""))
    except AppError as e:
        return render_template("login.html", error=e.message, form=f, next=f.get("next")), e.status
    login_user(user, remember=bool(f.get("remember")))
    return redirect(safe_next(f.get("next")) or url_for("web.perfil"))


@bp.post("/sair")
def sair():
    check_csrf()
    logout_user()
    return redirect(url_for("web.inicio"))


@bp.get("/perfil")
@login_required
def perfil():
    user = current_user()
    svc = AccountService()
    farm = svc.farm_view(user)
    lavouras = []
    if farm:
        rs = RecommendationService()
        for c in farm["crops"]:
            try:
                rec = rs.planting_advice(municipality=farm["municipality"]["ibge_code"], crop=c["slug"],
                                         soil=str(farm["soil_group"] or ""), level=user.language_level)
            except AppError:
                continue
            lavouras.append({"crop": c, "status": rec["status"], "risk_level": rec["risk_level"],
                             "title": rec["title"], "window": (rec.get("recommended_window") or {}).get("label"),
                             "link": url_for("web.clima", municipality=farm["municipality"]["ibge_code"],
                                             crop=c["slug"], soil=farm["soil_group"] or "")})
    return render_template("perfil.html", user=user, farm=farm, lavouras=lavouras,
                           crops=catalog_repo.list_crops(), soils=CropService().soils(),
                           novo=request.args.get("novo"), season=_season())


def _season() -> str | None:
    from app.repositories import zarc_repo

    v = zarc_repo.current()
    return v.version_label if v else None


def _json_error(e: AppError):
    return jsonify({"error": {"code": e.code, "message": e.message, "details": e.details}}), e.status


@bp.post("/perfil/propriedade")
@login_required
def salvar_propriedade():
    check_csrf()
    d = request.get_json(silent=True) or {}
    svc = AccountService()
    try:
        svc.save_farm(current_user(), place=d.get("place", ""), area_ha=d.get("area_ha"),
                      soil_group=d.get("soil_group"), crops=d.get("crops") or [], name=d.get("name"))
    except AppError as e:
        return _json_error(e)
    return jsonify({"ok": True, "farm": svc.farm_view(current_user())})


@bp.post("/perfil/preferencias")
@login_required
def salvar_preferencias():
    check_csrf()
    d = request.get_json(silent=True) or {}
    AccountService().update_preferences(current_user(), theme=d.get("theme"), font_size=d.get("font_size"),
                                        language_level=d.get("language_level"), name=d.get("name"))
    return jsonify({"ok": True})


@bp.post("/perfil/email")
@login_required
def trocar_email():
    check_csrf()
    d = request.get_json(silent=True) or {}
    try:
        AccountService().change_email(current_user(), d.get("email", ""))
    except AppError as e:
        return _json_error(e)
    return jsonify({"ok": True, "email": current_user().email})


@bp.get("/perfil/meus-dados")
@login_required
def meus_dados():
    """LGPD: acesso aos próprios dados (download em JSON)."""
    resp = jsonify(AccountService().export(current_user()))
    resp.headers["Content-Disposition"] = "attachment; filename=meus-dados-plantfacil.json"
    return resp


@bp.post("/perfil/excluir")
@login_required
def excluir_conta():
    """LGPD: eliminação dos dados a pedido do titular."""
    check_csrf()
    AccountService().delete(current_user())
    logout_user()
    return redirect(url_for("web.inicio", conta_excluida=1))


@bp.post("/assistente/mensagem")
@limiter.limit("30 per minute")
def assistente_mensagem():
    check_csrf()
    d = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()[:500]
    if not text:
        return jsonify({"error": {"code": "validation_error", "message": "Escreva uma pergunta."}}), 422
    try:
        return jsonify(ChatService().reply(text, d.get("context") or {}, current_user()))
    except AppError as e:
        return jsonify({"text": e.message, "intent": "error", "suggestions": [], "context": d.get("context") or {}})
