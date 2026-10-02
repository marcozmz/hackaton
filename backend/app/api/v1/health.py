from flask import Blueprint, jsonify
from sqlalchemy import text

from app.domain.engine import ENGINE_VERSION
from app.extensions import db, limiter
from app.repositories import zarc_repo


def register(bp: Blueprint) -> None:
    @bp.get("/health")
    @limiter.exempt
    def health():
        db.session.execute(text("SELECT 1"))
        z = zarc_repo.current()
        return jsonify(
            {
                "status": "ok",
                "engine_version": ENGINE_VERSION,
                "zarc_loaded": z is not None,
                "zarc_version": z.version_label if z else None,
            }
        )
