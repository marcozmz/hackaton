"""Aba Planejamento (calendário do Raul) com dados reais."""
from __future__ import annotations

from datetime import date

from flask import jsonify, redirect, render_template, request, url_for

from app.errors import AppError
from app.extensions import limiter
from app.repositories import catalog_repo
from app.security.auth import check_csrf, current_user, login_required
from app.services.crop_service import CropService
from app.services.location_service import LocationService
from app.services.planning_service import PlanningService
from app.web import _defaults, bp


def _parse_month(value: str | None, today: date) -> tuple[int, int]:
    try:
        y, m = (int(x) for x in (value or "").split("-"))
        if 1 <= m <= 12 and 2000 <= y <= 2100:
            return y, m
    except ValueError:
        pass
    return today.year, today.month


@bp.get("/planejamento")
def planejamento():
    d = _defaults()
    args = request.args
    loc_ibge = args.get("municipality") or d.get("municipality")
    crop_q = args.get("crop") or d.get("crop")
    if not loc_ibge or not crop_q:
        return redirect(url_for("web.inicio", nova=1))
    soil = args.get("soil", d.get("soil", ""))
    try:
        m = LocationService().by_ibge(int(loc_ibge)).municipality
        crops = CropService()
        crop = crops.resolve(crop_q, m.uf)
        soil_ref = crops.resolve_soil(soil)
    except (AppError, ValueError):
        return redirect(url_for("web.inicio", nova=1))
    today = date.today()
    year, month = _parse_month(args.get("mes"), today)
    selected = None
    if args.get("dia"):
        try:
            selected = date.fromisoformat(args["dia"])
            year, month = selected.year, selected.month
        except ValueError:
            selected = None
    user = current_user()
    svc = PlanningService()
    cal = svc.month(m, crop, soil_ref.group_code if soil_ref else None, year, month, selected, user)
    farm_crops = []
    if user and user.farm:
        farm_crops = [catalog_repo.crop_by_id(p.crop_id) for p in user.farm.plantings]
    candidates = farm_crops or catalog_repo.list_crops()
    refs = [crops.resolve(c.slug, m.uf) for c in candidates]
    windows = svc.next_windows(m, refs, soil_ref.group_code if soil_ref else None, today)
    return render_template(
        "planejamento.html", cal=cal, place=m, crop=crop, soil=soil_ref, soil_param=soil,
        crops=catalog_repo.list_crops(), windows=windows, windows_scope="suas culturas" if farm_crops else "todas as culturas",
        season=_season(), today=today,
    )


def _season() -> str | None:
    from app.repositories import zarc_repo

    v = zarc_repo.current()
    return v.version_label if v else None


def _task_json(t) -> dict:
    return {"id": t.id, "date": t.on_date.isoformat(), "title": t.title, "done": t.done}


@bp.post("/planejamento/atividades")
@login_required
@limiter.limit("60 per minute")
def nova_atividade():
    check_csrf()
    d = request.get_json(silent=True) or {}
    try:
        t = PlanningService.add_task(current_user(), d.get("date"), d.get("title"), d.get("crop"))
    except AppError as e:
        return jsonify({"error": {"code": e.code, "message": e.message}}), e.status
    return jsonify(_task_json(t)), 201


@bp.post("/planejamento/atividades/<int:task_id>/feito")
@login_required
def atividade_feita(task_id: int):
    check_csrf()
    d = request.get_json(silent=True) or {}
    try:
        t = PlanningService().set_done(current_user(), task_id, bool(d.get("done")))
    except AppError as e:
        return jsonify({"error": {"code": e.code, "message": e.message}}), e.status
    return jsonify(_task_json(t))


@bp.post("/planejamento/atividades/<int:task_id>/excluir")
@login_required
def excluir_atividade(task_id: int):
    check_csrf()
    try:
        PlanningService().delete_task(current_user(), task_id)
    except AppError as e:
        return jsonify({"error": {"code": e.code, "message": e.message}}), e.status
    return jsonify({"ok": True})
