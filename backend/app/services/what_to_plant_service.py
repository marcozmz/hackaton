"""'O que plantar agora?': todas as culturas do catálogo ordenadas pela situação de hoje.

Para o município e tipo de terra: está no período oficial (e com qual risco)? se não, quando abre?
Dentro do período, usa a mesma otimização do melhor dia de semeadura (ZARC + previsão).
"""
from __future__ import annotations

from datetime import date

from flask import current_app

from app.domain import decendio as dec
from app.domain import planning, sowing
from app.domain.context import MunicipalityRef, ZoneFacts
from app.domain.narrative.narrator import Narrator, date_text, weekday_date_text
from app.domain.zarc import combine
from app.errors import AppError
from app.repositories import catalog_repo, zarc_repo
from app.services.weather_service import WeatherService

SOON_DAYS = 45  # "abre em breve"

STATUS_TEXT = {
    "now": "Dá para plantar agora",
    "soon": "Abre em breve",
    "later": "Mais para frente",
    "no_data": "Sem zoneamento oficial aqui",
}


class WhatToPlantService:
    def rank(self, m: MunicipalityRef, soil_group: int | None, today: date | None = None) -> dict:
        today = today or date.today()
        codes = catalog_repo.soil_codes_for_group(soil_group) if soil_group else None
        forecast = []
        if WeatherService().enabled():
            try:
                forecast = list(WeatherService().forecast(m).days)
            except AppError:
                forecast = []
        narrator = Narrator()
        items = []
        for crop in catalog_repo.list_crops():
            _, rows = zarc_repo.zones(m.ibge_code, crop.id, codes, current_app.config["ZARC_DEFAULT_MANAGEMENT"])
            item = {"crop": {"slug": crop.slug, "name": crop.official_name}, "status": "no_data",
                    "risk_pct": None, "window": None, "start": None, "start_text": None, "best_day": None,
                    "days_until": None}
            if rows:
                windows = combine([ZoneFacts(**r) for r in rows]).windows
                w = planning.current_or_next_window(windows, today)
                if w:
                    now_risk = windows.get(dec.from_date(today))
                    days_until = (w.start - today).days
                    status = "now" if now_risk else ("soon" if days_until <= SOON_DAYS else "later")
                    item.update({"status": status, "risk_pct": now_risk or w.risk_min, "window": w.label,
                                 "start": w.start.isoformat(), "start_text": date_text(w.start.isoformat()),
                                 "days_until": None if status == "now" else days_until})
                    if status == "now" and forecast:
                        b = sowing.best_day(sowing.score_days(windows, forecast, today))
                        if b:
                            item["best_day"] = {"date": b.date.isoformat(), "label": weekday_date_text(b.date.isoformat()),
                                                "reasons": narrator.sowing_reason_texts(b.reasons)}
                else:
                    item["status"] = "later"
            item["status_text"] = STATUS_TEXT[item["status"]]
            items.append(item)

        order = {"now": 0, "soon": 1, "later": 2, "no_data": 3}
        items.sort(key=lambda i: (order[i["status"]],
                                  i["risk_pct"] or 99 if i["status"] == "now" else 0,
                                  i["best_day"] is None,
                                  i["days_until"] if i["days_until"] is not None else 999,
                                  i["crop"]["name"]))
        now = [i for i in items if i["status"] == "now"]
        soon = [i for i in items if i["status"] == "soon"]
        if now:
            extra = f" e mais {len(now) - 4}" if len(now) > 4 else ""
            summary = (f"Agora em {m.name} dá para plantar: "
                       + ", ".join(f'{i["crop"]["name"].lower()} (risco {i["risk_pct"]}%)' for i in now[:4]) + extra + ".")
        else:
            summary = f"Agora nenhuma das culturas está no período oficial de plantio em {m.name}."
        if soon:
            summary += " Em breve: " + ", ".join(f'{i["crop"]["name"].lower()} (a partir de {i["start_text"]})'
                                                for i in soon[:3]) + "."
        return {
            "location": {"ibge_code": m.ibge_code, "name": m.name, "uf": m.uf},
            "soil_group": soil_group,
            "as_of": today.isoformat(),
            "summary": summary,
            "items": items,
            "has_forecast": bool(forecast),
            "sources": ["zarc_tabua_risco"] + (["open_meteo"] if forecast else []),
        }
