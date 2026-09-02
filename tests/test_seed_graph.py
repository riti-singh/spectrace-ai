"""Operational graph seeding command tests."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.models import GraphCounts
from app.repositories import RepositoryError
from scripts import seed_graph as command
from tests.conftest import DATA_FILE


def settings_with_password() -> Settings:
    return Settings(
        _env_file=None,
        neo4j_password=SecretStr("test-password"),
        neo4j_database="neo4j",
    )


def counts() -> GraphCounts:
    return GraphCounts(
        nodes={"Requirement": 16, "Component": 7, "Risk": 7, "TestCase": 9},
        relationships={
            "DEPENDS_ON": 13,
            "APPLIES_TO": 39,
            "ADDRESSES": 18,
            "VERIFIES": 12,
        },
    )


def test_seed_graph_validates_seeds_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = Mock()
    repository.seed_dataset.return_value = counts()
    factory = Mock(return_value=repository)
    monkeypatch.setattr(command, "Neo4jRepository", factory)

    result = command.seed_graph(settings_with_password(), DATA_FILE, reset=True)

    assert result == counts()
    repository.seed_dataset.assert_called_once()
    assert repository.seed_dataset.call_args.kwargs == {"reset": True}
    repository.close.assert_called_once_with()


def test_seed_graph_requires_password_before_loading() -> None:
    with pytest.raises(RepositoryError, match="NEO4J_PASSWORD"):
        command.seed_graph(Settings(_env_file=None), Path("missing.json"))


def test_main_reports_counts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(command, "Settings", settings_with_password)
    monkeypatch.setattr(command, "seed_graph", lambda *_args, **_kwargs: counts())

    exit_code = command.main(["--data-file", str(DATA_FILE), "--reset"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Graph seed completed successfully" in output
    assert "Requirement: 16" in output
    assert "VERIFIES: 12" in output


def test_main_reports_repository_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(command, "Settings", settings_with_password)

    def fail(*_args: object, **_kwargs: object) -> GraphCounts:
        raise RepositoryError("database is offline")

    monkeypatch.setattr(command, "seed_graph", fail)

    assert command.main([]) == 1
    assert "Graph seeding failed: database is offline" in capsys.readouterr().err
