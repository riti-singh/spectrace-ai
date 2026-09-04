"""JSON repository behavior and integrity tests."""

import json
from pathlib import Path

import pytest

from app.repositories import JsonDataRepository
from app.repositories.json_repository import DatasetLoadError
from app.retrieval import EMBEDDING_DIMENSIONS, DeterministicSemanticEncoder
from tests.conftest import DATA_FILE
from tests.repository_contract import assert_asteria_repository_contract


def test_repository_returns_stably_sorted_records(repository: JsonDataRepository) -> None:
    assert [item.id for item in repository.list_requirements()] == [
        f"REQ-{number:03d}" for number in range(1, 17)
    ]
    assert repository.get_requirement("REQ-001") is not None
    assert repository.get_requirement("REQ-999") is None
    assert len(repository.list_components()) == 7
    assert len(repository.list_risks()) == 7
    assert len(repository.list_test_cases()) == 9


def test_json_repository_satisfies_shared_contract(
    repository: JsonDataRepository,
) -> None:
    assert_asteria_repository_contract(repository)


def test_json_repository_supplies_deterministic_retrieval_candidates(
    repository: JsonDataRepository,
) -> None:
    lexical = repository.lexical_candidates("thermal protection", ["Requirement"], 5)
    semantic = repository.semantic_candidates(
        DeterministicSemanticEncoder().encode("firmware recovery"),
        ["Requirement", "TestCase"],
        5,
    )
    graph = repository.graph_candidates(
        ["REQ-002"],
        ["Requirement"],
        ["DEPENDS_ON"],
        2,
        5,
    )

    assert lexical
    assert semantic
    assert graph
    assert graph == repository.graph_candidates(["REQ-002"], ["Requirement"], ["DEPENDS_ON"], 2, 5)


def test_json_retrieval_rejects_partial_and_non_positive_matches(
    repository: JsonDataRepository,
) -> None:
    all_entity_types = ["Requirement", "Component", "Risk", "TestCase"]

    assert repository.lexical_candidates("rm", all_entity_types, 5) == []
    assert repository.semantic_candidates([0.0] * EMBEDDING_DIMENSIONS, all_entity_types, 5) == []


@pytest.mark.parametrize(
    ("collection", "field", "broken_id"),
    [
        ("requirements", "component_ids", "CMP-999"),
        ("requirements", "risk_ids", "RSK-999"),
        ("requirements", "dependency_ids", "REQ-999"),
        ("test_cases", "requirement_ids", "REQ-999"),
    ],
)
def test_repository_rejects_broken_dataset_references(
    tmp_path: Path, collection: str, field: str, broken_id: str
) -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    payload[collection][0][field].append(broken_id)
    broken_file = tmp_path / "broken.json"
    broken_file.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DatasetLoadError, match=r"unknown .* reference"):
        JsonDataRepository(broken_file)


def test_repository_rejects_duplicate_ids(tmp_path: Path) -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    payload["components"].append(payload["components"][0])
    broken_file = tmp_path / "duplicate.json"
    broken_file.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DatasetLoadError, match="duplicate component ID"):
        JsonDataRepository(broken_file)


def test_repository_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DatasetLoadError, match="dataset file not found"):
        JsonDataRepository(tmp_path / "missing.json")


def test_repository_reports_invalid_json(tmp_path: Path) -> None:
    broken_file = tmp_path / "invalid.json"
    broken_file.write_text("{not valid", encoding="utf-8")

    with pytest.raises(DatasetLoadError, match="invalid JSON"):
        JsonDataRepository(broken_file)
