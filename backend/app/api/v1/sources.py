from flask import Blueprint, jsonify

from app.services.source_service import SourceService


def register(bp: Blueprint) -> None:
    @bp.get("/sources")
    def sources():
        return jsonify({"items": SourceService().list()})
