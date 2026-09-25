"""Конфігурація застосунку зі змінних оточення (префікс TENDOOR_)."""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TENDOOR_", env_file=".env", extra="ignore")

    env: str = "dev"
    postgres_dsn: str = "postgresql+asyncpg://tendoor:tendoor@localhost:5432/tendoor"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "tendoor"
    cors_origins: list[str] = ["http://localhost:5173"]

    # dev-значення; у будь-якому іншому середовищі обов'язково задати TENDOOR_JWT_SECRET
    jwt_secret: str = DEV_JWT_SECRET
    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 7
    cookie_secure: bool = False  # True за HTTPS
    login_max_failures: int = 5
    login_lock_minutes: int = 5

    prozorro_url: str = "https://public-api.prozorro.gov.ua/api/2.5"
    prozorro_concurrency: int = 16
    worker_poll_seconds: float = 5.0
    model_dir: str = "data/models"  # артефакти запусків конвеєра

    @field_validator("postgres_dsn")
    @classmethod
    def _asyncpg_dsn(cls, v: str) -> str:
        """Хмарні провайдери (Railway, Render) видають postgres:// або postgresql:// — драйвер asyncpg."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v.removeprefix(prefix)
        return v

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.env != "dev":
            if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("TENDOOR_JWT_SECRET: задайте власний секрет (щонайменше 32 символи)")
            if not self.cookie_secure:
                raise ValueError("TENDOOR_COOKIE_SECURE має бути true поза локальним середовищем (HTTPS)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
