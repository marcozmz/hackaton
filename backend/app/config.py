"""Configuração por ambiente (variáveis de ambiente)."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
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
