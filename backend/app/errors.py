"""Exceções de domínio + envelope de erro único da API."""
from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class AppError(Exception):
    code = "app_error"
    status = 400
    message = "Erro."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class LocationNotFound(AppError):
    code, status, message = "location_not_found", 404, "Não encontramos esse lugar."


class LocationAmbiguous(AppError):
    code, status, message = "location_ambiguous", 409, "Qual destes lugares você quer dizer?"


class CropNotFound(AppError):
    code, status, message = "crop_not_found", 404, "Não encontramos essa cultura."


class CropAmbiguous(AppError):
    code, status, message = "crop_ambiguous", 409, "Qual destas culturas você quer dizer?"


class SoilNotFound(AppError):
    code, status, message = "validation_error", 422, "Tipo de solo inválido."


class UpstreamUnavailable(AppError):
    code, status, message = "upstream_unavailable", 503, "Serviço externo indisponível no momento."


def _envelope(code: str, message: str, status: int, details: dict | None = None):
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return jsonify(body), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def _app_error(e: AppError):
        return _envelope(e.code, e.message, e.status, e.details)

    @app.errorhandler(ValidationError)
    def _validation(e: ValidationError):
        details = {"fields": [{"loc": ".".join(map(str, er["loc"])), "msg": er["msg"]} for er in e.errors()]}
        return _envelope("validation_error", "Parâmetros inválidos.", 422, details)

    @app.errorhandler(429)
    def _rate(e):
        return _envelope("rate_limited", "Muitas requisições. Tente de novo em instantes.", 429)

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        return _envelope(e.name.lower().replace(" ", "_"), e.description or e.name, e.code or 500)

    @app.errorhandler(Exception)
    def _unhandled(e: Exception):  # pragma: no cover
        log.exception("erro não tratado")
        return _envelope("internal_error", "Erro interno.", 500)
