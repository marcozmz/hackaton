"""Escolhe a implementação de cada provider pela config. Services só conhecem a interface."""
from __future__ import annotations

from flask import Flask, current_app

from app.providers.geocoding.base import NullCepProvider
from app.providers.geocoding.viacep import ViaCepProvider
from app.providers.weather.open_meteo import FixtureWeatherProvider, OpenMeteoProvider


def _weather(app: Flask):
    kind = app.config.get("WEATHER_PROVIDER", "open_meteo")
    if kind == "open_meteo":
        return OpenMeteoProvider(timeout=app.config["WEATHER_TIMEOUT"])
    if kind == "fixture":
        return FixtureWeatherProvider(app.config["WEATHER_FIXTURE"])
    return None


def init_providers(app: Flask) -> None:
    cep = app.config.get("GEOCODING_CEP_PROVIDER", "viacep")
    app.extensions["providers"] = {
        "cep": ViaCepProvider(timeout=app.config["HTTP_TIMEOUT"]) if cep == "viacep" else NullCepProvider(),
        "weather": _weather(app),  # None = previsão desligada
        # desejável: "llm": NullLLM()
    }


def provider(name: str):
    return current_app.extensions["providers"][name]
