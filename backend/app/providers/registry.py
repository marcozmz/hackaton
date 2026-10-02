"""Escolhe a implementação de cada provider pela config. Services só conhecem a interface."""
from __future__ import annotations

from flask import Flask, current_app

from app.providers.geocoding.base import NullCepProvider
from app.providers.geocoding.viacep import ViaCepProvider


def init_providers(app: Flask) -> None:
    cep = app.config.get("GEOCODING_CEP_PROVIDER", "viacep")
    app.extensions["providers"] = {
        "cep": ViaCepProvider(timeout=app.config["HTTP_TIMEOUT"]) if cep == "viacep" else NullCepProvider(),
        # desejável: "weather": OpenMeteoProvider(...), "llm": NullLLM()
    }


def provider(name: str):
    return current_app.extensions["providers"][name]
