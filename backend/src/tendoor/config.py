"""Конфігурація застосунку зі змінних оточення (префікс TENDOOR_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TENDOOR_", env_file=".env", extra="ignore")

    env: str = "dev"
    postgres_dsn: str = "postgresql+asyncpg://tendoor:tendoor@localhost:5432/tendoor"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "tendoor"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
