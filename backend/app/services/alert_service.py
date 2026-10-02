"""Aviso diário por e-mail: o backend manda os dados de cada agricultor que aceitou ao webhook do Make.com,
e o cenário do Make monta e envia o e-mail.

LGPD: só vai quem marcou o opt-in no perfil; vai o mínimo (nome, e-mail, coordenada do centro do município —
não guardamos a da roça — e a cultura). O Make é operador; desmarcar ou excluir a conta para o envio.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from flask import Flask, current_app

from app.errors import AppError
from app.extensions import db
from app.models.farmer import User
from app.models.provenance import utcnow
from app.repositories import catalog_repo, territory_repo

log = logging.getLogger(__name__)

BRT = timezone(timedelta(hours=-3))  # Brasília (sem horário de verão desde 2019)


class AlertError(AppError):
    status = 400
    code = "alert_error"


class AlertService:
    def enabled(self) -> bool:
        return bool(current_app.config.get("MAKE_WEBHOOK_URL"))

    # --- opt-in ---------------------------------------------------------------
    def set_opt_in(self, user: User, on: bool) -> None:
        if on and user.email_alerts_since is None:
            user.email_alerts_since = utcnow()
        elif not on:
            user.email_alerts_since = None
        db.session.commit()

    # --- conteúdo -------------------------------------------------------------
    def payload(self, user: User) -> dict | None:
        """Campos combinados com o cenário do Make. None = sem roça/cultura para avisar."""
        farm = user.farm
        if farm is None or not farm.plantings:
            return None
        m = territory_repo.get(farm.municipality_ibge)
        crops = [catalog_repo.crop_by_id(p.crop_id) for p in farm.plantings]
        main = crops[0]
        data = {
            "nome": user.display_name,
            "email": user.email,
            "latitude": round(m.centroid_lat, 4),
            "longitude": round(m.centroid_lon, 4),
            "cultura": main.official_name,
            # extras (o cenário pode ignorar)
            "culturas": [c.official_name for c in crops],
            "municipio": f"{m.name} - {m.uf}",
            "data": datetime.now(BRT).date().isoformat(),
        }
        data.update(self._orientation(farm, main.slug, user.language_level))
        return data

    def _orientation(self, farm, crop_slug: str, level: str) -> dict:
        """Resumo da orientação oficial (ZARC + previsão) para o e-mail ter conteúdo nosso, não só o clima."""
        from app.services.recommendation_service import RecommendationService

        try:
            rec = RecommendationService().planting_advice(
                municipality=farm.municipality_ibge, crop=crop_slug, soil=str(farm.soil_group or ""), level=level)
        except AppError:
            return {}
        return {"situacao": rec["status"], "titulo": rec["title"], "mensagem": rec["summary"]}

    # --- envio ----------------------------------------------------------------
    def send(self, user: User) -> bool:
        url = current_app.config.get("MAKE_WEBHOOK_URL")
        if not url:
            raise AlertError("Avisos por e-mail ainda não estão ligados neste servidor.")
        data = self.payload(user)
        if data is None:
            raise AlertError("Cadastre sua roça e pelo menos uma cultura para receber o aviso.")
        r = requests.post(url, json=data, timeout=current_app.config["HTTP_TIMEOUT"])
        r.raise_for_status()
        return True

    def send_all(self) -> dict:
        users = db.session.scalars(db.select(User).where(User.email_alerts_since.is_not(None))).all()
        sent = skipped = failed = 0
        for u in users:
            try:
                self.send(u)
                sent += 1
            except AlertError:
                skipped += 1
            except requests.RequestException as e:  # um envio que falha não derruba os outros
                failed += 1
                log.warning("aviso por e-mail falhou (user=%s): %s", u.id, type(e).__name__)
        return {"enviados": sent, "sem_roca": skipped, "falhas": failed}


# --- disparo diário dentro do servidor ------------------------------------------
def _stamp_file(app: Flask) -> Path:
    return Path(app.instance_path) / "avisos_ultimo_envio.txt"


def run_daily_if_due(app: Flask, now: datetime | None = None) -> dict | None:
    """Envia uma vez por dia, entre ALERTS_HOUR e o meio-dia (Brasília): se o servidor estava desligado às 6h,
    manda quando ligar de manhã, mas nunca à tarde/noite. O carimbo em disco evita repetir ao reiniciar."""
    now = now or datetime.now(BRT)
    if not app.config["ALERTS_HOUR"] <= now.hour < 12:
        return None
    stamp = _stamp_file(app)
    today = now.date().isoformat()
    if stamp.exists() and stamp.read_text().strip() == today:
        return None
    stamp.write_text(today)
    with app.app_context():
        result = AlertService().send_all()
    log.info("avisos por e-mail de %s: %s", today, result)
    return result


def start_scheduler(app: Flask) -> None:
    def loop():
        while True:
            try:
                run_daily_if_due(app)
            except Exception:  # noqa: BLE001 — o agendador nunca pode morrer
                log.exception("agendador de avisos")
            time.sleep(60)

    threading.Thread(target=loop, name="avisos-email", daemon=True).start()
    log.info("agendador de avisos por e-mail ligado (todo dia às %sh, Brasília)", app.config["ALERTS_HOUR"])
