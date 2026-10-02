"""Planejamento: calendário do mês com a situação oficial (ZARC), chuva prevista e atividades."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from urllib.parse import quote

from flask import current_app
from sqlalchemy import and_, select

from app.domain import planning
from app.domain.context import CropRef, MunicipalityRef, ZoneFacts
from app.domain.decendio import MONTHS_FULL
from app.domain.narrative.narrator import Narrator, SafeDict, date_text
from app.domain.zarc import combine
from app.errors import AppError
from app.extensions import db
from app.models import FarmTask, User
from app.repositories import catalog_repo, zarc_repo
from app.services.weather_service import WeatherService

WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


class TaskError(AppError):
    code, status, message = "validation_error", 422, "Atividade inválida."


class TaskNotFound(AppError):
    code, status, message = "not_found", 404, "Atividade não encontrada."


def long_date(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()].capitalize()}, {d.day} de {MONTHS_FULL[d.month - 1]}"


class PlanningService:
    def __init__(self):
        self.m = Narrator().m["planning"]

    def _windows(self, m: MunicipalityRef, crop: CropRef, soil_group: int | None) -> tuple[dict[int, int], bool]:
        codes = catalog_repo.soil_codes_for_group(soil_group) if soil_group else None
        _, rows = zarc_repo.zones(m.ibge_code, crop.id, codes, current_app.config["ZARC_DEFAULT_MANAGEMENT"])
        if not rows:
            return {}, False
        return combine([ZoneFacts(**r) for r in rows]).windows, True

    def _forecast(self, m: MunicipalityRef) -> dict:
        svc = WeatherService()
        if not svc.enabled():
            return {}
        try:
            return {d.date: d for d in svc.forecast(m).days}
        except AppError:
            return {}

    def _suggestion_text(self, s: planning.Suggestion, crop: CropRef) -> dict:
        title, text = self.m["suggestions"][s.code]
        p = {**s.params, "crop": crop.name.lower()}
        if p.get("start"):
            p["start_text"] = date_text(p["start"])
        return {"code": s.code, "title": title.format_map(SafeDict(p)), "text": text.format_map(SafeDict(p))}

    def next_windows(self, m: MunicipalityRef, crops: list[CropRef], soil_group: int | None, today: date) -> list[dict]:
        out = []
        for c in crops:
            windows, has = self._windows(m, c, soil_group)
            w = planning.current_or_next_window(windows, today) if has else None
            out.append({
                "crop": {"slug": c.slug, "name": c.name},
                "has_zarc": has,
                "label": w.label if w else None,
                "start": w.start if w else None,
                "end": w.end if w else None,
                "start_text": date_text(w.start.isoformat()) if w else None,
                "is_current": w.is_current if w else False,
                "risk_min": w.risk_min if w else None,
            })
        # janelas abertas primeiro, depois as que abrem antes
        return sorted(out, key=lambda x: (not x["has_zarc"], not x["is_current"], x["start"] or date.max))

    def month(self, m: MunicipalityRef, crop: CropRef, soil_group: int | None, year: int, month: int,
              selected: date | None, user: User | None, today: date | None = None) -> dict:
        today = today or date.today()
        windows, has_zarc = self._windows(m, crop, soil_group)
        forecast = self._forecast(m)
        first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        tasks = self.tasks(user, first - timedelta(days=7), last + timedelta(days=7)) if user else []
        counts: dict[date, tuple[int, int]] = {}
        for t in tasks:
            total, done = counts.get(t.on_date, (0, 0))
            counts[t.on_date] = (total + 1, done + int(t.done))
        if selected is None:
            selected = today if (today.year, today.month) == (year, month) else first
        weeks = planning.month_grid(year, month, windows, has_zarc, forecast, today, selected, counts)
        cell = next(c for w in weeks for c in w if c.date == selected) if any(
            c.date == selected for w in weeks for c in w) else None
        window = planning.current_or_next_window(windows, selected) if has_zarc else None
        _, varieties = catalog_repo.varieties_for(crop.id, m.uf)
        fc_day = forecast.get(selected)
        suggestions = [self._suggestion_text(s, crop) for s in planning.day_suggestions(cell, fc_day, window, len(varieties))] if cell else []
        day_tasks = [t for t in tasks if t.on_date == selected]
        prev_m = (first - timedelta(days=1)).replace(day=1)
        next_m = last + timedelta(days=1)
        month_cells = [c for w in weeks for c in w if c.in_month]
        return {
            "title": f"{MONTHS_FULL[month - 1].capitalize()} {year}",
            "subtitle": self._month_subtitle(month_cells),
            "weeks": weeks,
            "levels": self.m["levels"],
            "rain_legend": self.m["rain_legend"],
            "has_zarc": has_zarc,
            "has_forecast": bool(forecast),
            "prev": prev_m.strftime("%Y-%m"),
            "next": next_m.strftime("%Y-%m"),
            "selected": {
                "date": selected,
                "label": long_date(selected),
                "level": cell.level if cell else None,
                "level_text": self.m["levels"][cell.level] if cell else None,
                "risk": cell.risk_pct if cell else None,
                "forecast": fc_day,
                "suggestions": suggestions,
                "tasks": day_tasks,
            },
            "window": window,
            "google_calendar_url": self._gcal(m, crop, selected, suggestions, day_tasks),
        }

    def _month_subtitle(self, cells: list[planning.DayCell]) -> str:
        ideal = sum(1 for c in cells if c.level == "ideal")
        attn = sum(1 for c in cells if c.level == "attention")
        if ideal or attn:
            return f"{ideal} dias de plantio indicado com risco baixo · {attn} com atenção"
        if any(c.level == "prep" for c in cells):
            return "Mês de preparar a terra: o período de plantio começa em seguida"
        if any(c.level == "no_data" for c in cells):
            return "Sem zoneamento oficial para esta cultura aqui"
        return "Fora do período de plantio neste mês"

    @staticmethod
    def _gcal(m: MunicipalityRef, crop: CropRef, d: date, suggestions: list[dict], tasks: list[FarmTask]) -> str:
        items = [t.title for t in tasks] or [s["title"] for s in suggestions]
        details = "Plant+Facil — planejamento de " + crop.name + ":\n" + "\n".join(f"- {i}" for i in items)
        day = d.strftime("%Y%m%d")
        nxt = (d + timedelta(days=1)).strftime("%Y%m%d")
        return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
                f"&text={quote('Plant+Facil: ' + crop.name)}&dates={day}/{nxt}"
                f"&details={quote(details)}&location={quote(m.name + ' - ' + m.uf)}")

    # --- atividades do usuário (dono = usuário logado) --------------------------
    @staticmethod
    def tasks(user: User, start: date, end: date) -> list[FarmTask]:
        q = select(FarmTask).where(and_(FarmTask.user_id == user.id, FarmTask.on_date >= start,
                                        FarmTask.on_date <= end)).order_by(FarmTask.on_date, FarmTask.id)
        return list(db.session.scalars(q))

    @staticmethod
    def add_task(user: User, on_date: str, title: str, crop_slug: str | None) -> FarmTask:
        title = (title or "").strip()[:120]
        if not title:
            raise TaskError("Escreva o que vai fazer.")
        try:
            d = date.fromisoformat(on_date)
        except (TypeError, ValueError):
            raise TaskError("Data inválida.") from None
        crop = catalog_repo.crop_by_slug(crop_slug) if crop_slug else None
        t = FarmTask(user_id=user.id, on_date=d, title=title, crop_id=crop.id if crop else None)
        db.session.add(t)
        db.session.commit()
        return t

    @staticmethod
    def _own(user: User, task_id: int) -> FarmTask:
        t = db.session.get(FarmTask, task_id)
        if t is None or t.user_id != user.id:  # de outro usuário = "não existe"
            raise TaskNotFound()
        return t

    def set_done(self, user: User, task_id: int, done: bool) -> FarmTask:
        t = self._own(user, task_id)
        t.done = bool(done)
        db.session.commit()
        return t

    def delete_task(self, user: User, task_id: int) -> None:
        db.session.delete(self._own(user, task_id))
        db.session.commit()
