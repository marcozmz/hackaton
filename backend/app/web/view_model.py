"""Adapta o dicionário da recomendação ao que a tela `clima.html` desenha.

Só apresentação (ícone, cor da paleta, rótulo curto). Nenhuma regra agronômica aqui:
tudo que é decisão já veio pronto do engine.
"""
from __future__ import annotations

from datetime import datetime

STATUS_STYLE = {
    # status → (ícone, classe de borda, classe do selo, classe do fundo do ícone, classe do texto)
    "favorable": ("check_circle", "border-secondary", "bg-secondary text-on-secondary",
                  "bg-secondary-container text-on-secondary-container", "text-secondary"),
    "attention": ("warning", "border-tertiary-fixed-dim", "bg-tertiary-fixed-dim text-on-tertiary-fixed",
                  "bg-tertiary-fixed text-on-tertiary-fixed", "text-on-tertiary-fixed-variant"),
    "unfavorable": ("block", "border-error", "bg-error text-on-error",
                    "bg-error-container text-on-error-container", "text-error"),
    "no_data": ("help", "border-outline", "bg-surface-container-high text-on-surface",
                "bg-surface-container-high text-on-surface", "text-on-surface-variant"),
}
RISK_LABEL = {"low": "Risco baixo", "medium": "Risco médio", "high": "Risco alto", "unknown": "Sem dado oficial"}

CONDITION = {
    # condição → (ícone, selo, classe do selo, card de alerta?)
    "heavy_rain": ("thunderstorm", "Alerta", "bg-error-container text-on-error-container", True),
    "moderate_rain": ("rainy", "Atenção", "bg-tertiary-fixed text-on-tertiary-fixed", False),
    "rain": ("rainy", "Chuva", "bg-surface-container-high text-on-surface", False),
    "light_rain": ("partly_cloudy_day", "Chuvisco", "bg-surface-container-high text-on-surface", False),
    "dry": ("sunny", "Seco", "bg-surface-container-high text-on-surface", False),
}

ALERT_TITLES = {
    "forecast_heavy_rain": ("Chuva forte prevista", "thunderstorm", "error"),
    "forecast_dry_spell": ("Pouca chuva nos próximos dias", "water_drop", "tertiary"),
    "zarc_window_closing": ("O período de plantio está acabando", "hourglass_bottom", "tertiary"),
    "zarc_out_of_window": ("Fora do período de plantio", "event_busy", "error"),
    "zarc_no_window": ("Sem período indicado", "event_busy", "error"),
    "zarc_no_coverage": ("Sem zoneamento oficial", "help", "outline"),
    "soil_unspecified": ("Tipo de terra não informado", "terrain", "outline"),
    "forecast_unavailable": ("Previsão indisponível agora", "cloud_off", "outline"),
}
MOISTURE_CODES = ("forecast_good_moisture", "forecast_dry_spell")


def _day_label(iso: str, idx: int, weekday: str) -> str:
    return f"Hoje ({weekday[:3].capitalize()})" if idx == 0 else f"{weekday.capitalize()}"


def clima_view(rec: dict) -> dict:
    icon, border, badge, icon_bg, text_cls = STATUS_STYLE[rec["status"]]
    w = rec.get("recommended_window") or {}
    # Nível geral (pior achado: ZARC, previsão...). O % do ZARC aparece na linha da janela.
    risk_label = RISK_LABEL[rec["risk_level"]]

    fc = rec.get("forecast") or {}
    days = []
    for i, d in enumerate(fc.get("days") or []):
        ic, tag, tag_cls, alert = CONDITION[d["condition"]]
        days.append({**d, "title": _day_label(d["date"], i, d["weekday"]), "icon": ic, "tag": tag,
                     "tag_cls": tag_cls, "alert": alert, "today": i == 0})
    updated = None
    if fc.get("fetched_at"):
        updated = datetime.fromisoformat(fc["fetched_at"]).astimezone().strftime("%H:%M")

    why = rec["explanation"]["why"]
    alerts = []
    for r in why:
        if r["code"] in ALERT_TITLES and r["severity"] in ("attention", "high", "blocking", "info"):
            title, ic, tone = ALERT_TITLES[r["code"]]
            alerts.append({"title": title, "icon": ic, "tone": tone, "text": r["text"],
                           "detail": (r.get("data_used") or [None])[0],
                           "source": (r.get("source") or {}).get("name")})
    moisture = next((r for r in why if r["code"] in MOISTURE_CODES), None)

    speech = " ".join([rec["title"] + ".", rec["summary"], *rec["actions"][:3]])
    return {
        "status_icon": icon, "border": border, "badge": badge, "icon_bg": icon_bg, "text_cls": text_cls,
        "risk_label": risk_label,
        "window": w,
        "days": days[:7],
        "today": days[0] if days else None,
        "forecast_updated": updated,
        "alerts": alerts,
        "moisture": moisture,
        "speech": speech,
        "gps": rec["location"]["resolved_by"] == "nearest_centroid",
        "zarc_source": next((s for s in rec["sources"] if s["id"] == "zarc_tabua_risco"), None),
    }
