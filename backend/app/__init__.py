"""Plante Fácil — backend (monólito modular Flask, API-first)."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from flask import Flask

from app.config import CONFIGS, INSTANCE_DIR
from app.errors import register_error_handlers
from app.extensions import cache, compress, cors, db, limiter, migrate


def create_app(env: str | None = None) -> Flask:
    load_dotenv()
    env = env or os.getenv("APP_ENV", "development")
    cfg = CONFIGS[env]
    if hasattr(cfg, "validate"):
        cfg.validate()

    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.from_object(cfg)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.json.compact = True  # GeoJSON grande: sem indentação nem em dev
    INSTANCE_DIR.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from app import models  # noqa: F401  (registra os models no metadata)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    cache.init_app(app)
    compress.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from app.providers.registry import init_providers

    init_providers(app)

    from app.api.v1 import create_blueprint

    app.register_blueprint(create_blueprint())
    register_error_handlers(app)

    from app.tasks.cli import data_cli

    app.cli.add_command(data_cli)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp

    return app
