"""Configuração por ambiente (variáveis de ambiente)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Carrega o .env ANTES de os atributos abaixo lerem os.getenv (senão o .env é ignorado).
load_dotenv(BASE_DIR / ".env")
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    ENV = "development"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'plantefacil.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Cache (Flask-Caching). SimpleCache no MVP; Redis depois, mesma interface.
    CACHE_TYPE = os.getenv("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = 300
    RECOMMENDATION_CACHE_TTL = int(os.getenv("RECOMMENDATION_CACHE_TTL", "1800"))

    # Rate limit (Flask-Limiter), memória no MVP.
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "60 per minute")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    CORS_ORIGINS = [o for o in os.getenv("CORS_ORIGINS", "*").split(",") if o]

    # Providers
    GEOCODING_CEP_PROVIDER = os.getenv("GEOCODING_CEP_PROVIDER", "viacep")  # viacep | none
    WEATHER_PROVIDER = os.getenv("WEATHER_PROVIDER", "open_meteo")  # open_meteo | fixture | none
    WEATHER_TIMEOUT = (5, 15)
    WEATHER_FIXTURE = os.getenv(
        "WEATHER_FIXTURE", str(BASE_DIR / "app" / "providers" / "weather" / "fixtures" / "open_meteo_araraquara.json")
    )
    FORECAST_TTL_SECONDS = int(os.getenv("FORECAST_TTL_SECONDS", "10800"))  # 3 h
    FORECAST_STALE_MAX_SECONDS = 24 * 3600  # provider fora: aceita run antigo até 24 h (degradado)
    FORECAST_DAYS = 10
    # IA (desejável): só reescreve. gemini | ollama | none. Sem chave → none (templates).
    LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini" if os.getenv("LLM_API_KEY", "").strip() else "none")
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")  # ~1 s; 2.5/2.0 foram aposentados
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "12"))
    LLM_MAX_TOKENS = 400
    LLM_CACHE_TTL = 24 * 3600
    GEO_DIR = os.getenv("GEO_DIR", str(INSTANCE_DIR / "geo"))  # malhas IBGE por UF (fora do git)
    HTTP_TIMEOUT = (3, 8)

    # Domínio
    ZARC_DEFAULT_MANAGEMENT = int(os.getenv("ZARC_DEFAULT_MANAGEMENT", "1"))  # 1 = sequeiro
    DEFAULT_LANGUAGE_LEVEL = "simple"
    DEBUG_PAYLOADS = os.getenv("DEBUG_PAYLOADS", "0") == "1"


class DevelopmentConfig(Config):
    DEBUG = True
    DEBUG_PAYLOADS = True


class TestingConfig(Config):
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    CACHE_TYPE = "NullCache"
    RATELIMIT_ENABLED = False
    GEOCODING_CEP_PROVIDER = "none"
    WEATHER_PROVIDER = "fixture"
    LLM_PROVIDER = "none"


class ProductionConfig(Config):
    ENV = "production"
    DEBUG = False

    @classmethod
    def validate(cls) -> None:
        if cls.SECRET_KEY == "dev-only-change-me":
            raise RuntimeError("SECRET_KEY obrigatório em produção")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
