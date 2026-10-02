"""Escolhe a implementação de cada provider pela config. Services só conhecem a interface."""
from __future__ import annotations

from flask import Flask, current_app

from app.providers.geocoding.base import NullCepProvider
from app.providers.geocoding.viacep import ViaCepProvider
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.ollama import OllamaProvider
from app.providers.weather.open_meteo import FixtureWeatherProvider, OpenMeteoProvider


def _weather(app: Flask):
    kind = app.config.get("WEATHER_PROVIDER", "open_meteo")
    if kind == "open_meteo":
        return OpenMeteoProvider(timeout=app.config["WEATHER_TIMEOUT"])
    if kind == "fixture":
        return FixtureWeatherProvider(app.config["WEATHER_FIXTURE"])
    return None


def _llm(app: Flask):
    kind = app.config.get("LLM_PROVIDER", "none")
    if kind == "gemini" and app.config.get("LLM_API_KEY"):
        return GeminiProvider(app.config["LLM_API_KEY"], app.config["LLM_MODEL"])
    if kind == "ollama":
        return OllamaProvider(app.config["OLLAMA_MODEL"])
    return None  # sem IA: o produto funciona só com templates


def init_providers(app: Flask) -> None:
    cep = app.config.get("GEOCODING_CEP_PROVIDER", "viacep")
    app.extensions["providers"] = {
        "cep": ViaCepProvider(timeout=app.config["HTTP_TIMEOUT"]) if cep == "viacep" else NullCepProvider(),
        "weather": _weather(app),  # None = previsão desligada
        "llm": _llm(app),
    }


def provider(name: str):
    return current_app.extensions["providers"][name]
