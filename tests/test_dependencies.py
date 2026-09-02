"""Repository selection and API dependency translation tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import Settings
from app.core.dependencies import RepositoryManager, get_graph_service, get_repository
from app.repositories import Neo4jRepository, RepositoryConnectionError
from tests.conftest import DATA_FILE
from tests.fakes import FakeDriver


def test_repository_manager_reuses_and_closes_json_repository() -> None:
    manager = RepositoryManager(Settings(_env_file=None, data_file=DATA_FILE))

    first = manager.get()
    second = manager.get()
    manager.close()

    assert first is second
    assert manager.get() is not first


def test_repository_manager_builds_configured_neo4j(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, str] = {}

    class StubNeo4jRepository:
        def __init__(self, **kwargs: str) -> None:
            created.update(kwargs)

        def close(self) -> None:
            created["closed"] = "yes"

    monkeypatch.setattr("app.core.dependencies.Neo4jRepository", StubNeo4jRepository)
    settings = Settings(
        _env_file=None,
        repository_backend="neo4j",
        neo4j_uri="bolt://graph:7687",
        neo4j_username="spectrace",
        neo4j_password=SecretStr("secret"),
        neo4j_database="neo4j",
    )
    manager = RepositoryManager(settings)

    manager.get()
    manager.close()

    assert created == {
        "uri": "bolt://graph:7687",
        "username": "spectrace",
        "password": "secret",
        "database": "neo4j",
        "closed": "yes",
    }


def test_repository_manager_defensively_rejects_missing_password() -> None:
    settings = Settings.model_construct(
        repository_backend="neo4j",
        neo4j_password=None,
        neo4j_uri="bolt://graph:7687",
        neo4j_username="neo4j",
        neo4j_database="neo4j",
    )

    with pytest.raises(RepositoryConnectionError, match="password is not configured"):
        RepositoryManager(settings).get()


def test_connection_failure_is_translated_by_api_dependency() -> None:
    manager = Mock()
    manager.get.side_effect = RepositoryConnectionError("sensitive driver details")
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(repository_manager=manager))
    )

    with pytest.raises(HTTPException) as captured:
        get_repository(request)  # type: ignore[arg-type]

    assert captured.value.status_code == 503
    assert captured.value.detail["code"] == "repository_unavailable"
    assert "sensitive" not in captured.value.detail["message"]


def test_graph_service_dependency_accepts_graph_repository() -> None:
    repository = Neo4jRepository(
        "bolt://unused",
        "neo4j",
        "secret",
        "neo4j",
        driver=FakeDriver(),
        verify_connectivity=False,
    )

    service = get_graph_service(repository)

    assert service is not None
