"""Repository backend configuration tests."""

import pytest
from pydantic import ValidationError
from pydantic.types import SecretStr

from app.core.config import Settings


def test_json_is_the_default_backend() -> None:
    settings = Settings(_env_file=None)

    assert settings.repository_backend == "json"
    assert settings.neo4j_password is None


def test_invalid_backend_fails_fast() -> None:
    with pytest.raises(ValidationError, match="Input should be 'json' or 'neo4j'"):
        Settings(_env_file=None, repository_backend="invalid")


def test_neo4j_backend_requires_password() -> None:
    with pytest.raises(ValidationError, match="NEO4J_PASSWORD is required"):
        Settings(_env_file=None, repository_backend="neo4j")


def test_neo4j_programmatic_configuration() -> None:
    settings = Settings(
        _env_file=None,
        repository_backend="neo4j",
        neo4j_password=SecretStr("test-password"),
        neo4j_database="spectrace-test",
    )

    assert settings.neo4j_database == "spectrace-test"
    assert settings.neo4j_password is not None
    assert settings.neo4j_password.get_secret_value() == "test-password"


def test_standard_neo4j_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECTRACE_REPOSITORY_BACKEND", "neo4j")
    monkeypatch.setenv("NEO4J_URI", "bolt://database:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "integration")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")

    settings = Settings(_env_file=None)

    assert settings.neo4j_uri == "bolt://database:7687"
    assert settings.neo4j_username == "integration"
    assert settings.neo4j_password is not None
    assert settings.neo4j_password.get_secret_value() == "secret"
