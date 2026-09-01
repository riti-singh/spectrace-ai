"""Environment-aware application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SPECTRACE_",
        extra="ignore",
    )

    app_name: str = "Spectrace AI"
    environment: str = "development"
    data_file: Path = Field(default=PROJECT_ROOT / "data" / "asteria_dataset.json")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
