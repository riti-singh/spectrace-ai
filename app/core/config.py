"""Environment-aware application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SPECTRACE_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Spectrace AI"
    environment: str = "development"
    data_file: Path = Field(default=PROJECT_ROOT / "data" / "asteria_dataset.json")
    repository_backend: Literal["json", "neo4j"] = "json"
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        validation_alias=AliasChoices("NEO4J_URI", "SPECTRACE_NEO4J_URI"),
    )
    neo4j_username: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("NEO4J_USERNAME", "SPECTRACE_NEO4J_USERNAME"),
    )
    neo4j_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("NEO4J_PASSWORD", "SPECTRACE_NEO4J_PASSWORD"),
    )
    neo4j_database: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("NEO4J_DATABASE", "SPECTRACE_NEO4J_DATABASE"),
    )

    @model_validator(mode="after")
    def validate_backend_credentials(self) -> Self:
        if self.repository_backend == "neo4j" and (
            self.neo4j_password is None or not self.neo4j_password.get_secret_value()
        ):
            raise ValueError("NEO4J_PASSWORD is required when repository backend is neo4j")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
