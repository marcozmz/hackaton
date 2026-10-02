"""API v1. Controllers finos: validam entrada, chamam UM service, serializam."""
from flask import Blueprint

from app.api.v1 import crops, health, location, recommendations, sources, weather


def create_blueprint() -> Blueprint:
    bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
    for module in (health, location, crops, recommendations, sources, weather):
        module.register(bp)
    return bp
