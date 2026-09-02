"""Unit tests for Neo4j query execution, conversion, seeding, and failure translation."""

from typing import Any

import pytest
from neo4j import GraphDatabase, RoutingControl
from neo4j.exceptions import ConfigurationError, Neo4jError, ServiceUnavailable

from app.models import Dataset
from app.repositories import (
    Neo4jRepository,
    RepositoryConnectionError,
    RepositoryQueryError,
    load_dataset,
)
from app.repositories.neo4j_repository import (
    COMPONENTS_FOR_REQUIREMENT_QUERY,
    DEPENDENCY_CYCLES_QUERY,
    DOWNSTREAM_IMPACT_QUERY,
    GRAPH_COUNTS_QUERY,
    LIST_COMPONENTS_QUERY,
    LIST_REQUIREMENTS_QUERY,
    LIST_RISKS_QUERY,
    LIST_TEST_CASES_QUERY,
    ORPHAN_NODES_QUERY,
    REQUIREMENTS_FOR_COMPONENT_QUERY,
    SELF_PATH_QUERY,
    SHORTEST_PATH_QUERY,
    TRANSITIVE_DEPENDENCIES_QUERY,
    UNVERIFIED_RISKS_QUERY,
)
from tests.conftest import DATA_FILE
from tests.fakes import FakeDriver


def graph_count_record() -> dict[str, Any]:
    return {
        "node_pairs": [
            ["Requirement", 16],
            ["Component", 7],
            ["Risk", 7],
            ["TestCase", 9],
        ],
        "relationship_pairs": [
            ["DEPENDS_ON", 13],
            ["APPLIES_TO", 39],
            ["ADDRESSES", 18],
            ["VERIFIES", 12],
        ],
    }


def test_connectivity_uses_execute_query_and_explicit_database() -> None:
    driver = FakeDriver(lambda _query, _parameters: [{"ok": 1}])

    Neo4jRepository("bolt://unused", "neo4j", "secret", "spectrace", driver=driver)

    assert driver.calls[0]["query"] == "RETURN 1 AS ok"
    assert driver.calls[0]["database_"] == "spectrace"
    assert driver.calls[0]["routing_"] == RoutingControl.READ


def test_connectivity_requires_positive_result() -> None:
    repository = Neo4jRepository(
        "bolt://unused",
        "neo4j",
        "secret",
        "neo4j",
        driver=FakeDriver(),
        verify_connectivity=False,
    )

    with pytest.raises(RepositoryConnectionError, match="returned no result"):
        repository.verify_connectivity()


def test_requirement_query_is_parameterized_and_converted() -> None:
    entity = {
        "id": "REQ-001",
        "title": "Initial satellite acquisition",
        "normative_text": "The terminal shall acquire an authorized satellite deterministically.",
        "requirement_type": "performance",
        "priority": "critical",
        "source_section": "3.1.1 Acquisition",
        "verification_method": "test",
        "component_ids": ["CMP-003", "CMP-001", "CMP-002"],
        "risk_ids": ["RSK-001"],
        "dependency_ids": [],
    }
    driver = FakeDriver(lambda _query, _parameters: [{"entity": entity}])
    repository = Neo4jRepository(
        "bolt://unused", "neo4j", "secret", "neo4j", driver=driver, verify_connectivity=False
    )
    hostile_id = "REQ-001'}) MATCH (node) DETACH DELETE node //"

    requirement = repository.get_requirement(hostile_id)

    assert requirement is not None
    assert requirement.component_ids == ["CMP-001", "CMP-002", "CMP-003"]
    call = driver.calls[0]
    assert hostile_id not in call["query"]
    assert call["parameters_"] == {"requirement_id": hostile_id}
    assert call["database_"] == "neo4j"


def test_missing_requirement_returns_none() -> None:
    repository = Neo4jRepository(
        "bolt://unused",
        "neo4j",
        "secret",
        "neo4j",
        driver=FakeDriver(),
        verify_connectivity=False,
    )

    assert repository.get_requirement("REQ-999") is None


def test_read_and_graph_methods_convert_typed_records() -> None:
    dataset = load_dataset(DATA_FILE)
    requirement = dataset.requirements[0].model_dump(mode="json")
    component = dataset.components[0].model_dump(mode="json")
    risk = dataset.risks[0].model_dump(mode="json")
    test_case = dataset.test_cases[0].model_dump(mode="json")
    path = {
        "nodes": [
            {"id": "TST-001", "entity_type": "TestCase"},
            {"id": "REQ-001", "entity_type": "Requirement"},
        ],
        "relationship_types": ["VERIFIES"],
    }

    def handler(query: str, _parameters: object) -> list[dict[str, Any]]:
        if query in {
            LIST_REQUIREMENTS_QUERY,
            TRANSITIVE_DEPENDENCIES_QUERY,
            DOWNSTREAM_IMPACT_QUERY,
            REQUIREMENTS_FOR_COMPONENT_QUERY,
        }:
            return [{"entity": requirement}]
        if query in {LIST_COMPONENTS_QUERY, COMPONENTS_FOR_REQUIREMENT_QUERY}:
            return [{"entity": component}]
        if query in {LIST_RISKS_QUERY, UNVERIFIED_RISKS_QUERY}:
            return [{"entity": risk}]
        if query == LIST_TEST_CASES_QUERY:
            return [{"entity": test_case}]
        if query in {SHORTEST_PATH_QUERY, SELF_PATH_QUERY}:
            return [{"path": path}]
        if query == DEPENDENCY_CYCLES_QUERY:
            return [{"cycle": ["REQ-001", "REQ-002", "REQ-001"]}]
        if query == ORPHAN_NODES_QUERY:
            return [{"entity": {"id": "CMP-999", "entity_type": "Component"}}]
        return []

    repository = Neo4jRepository(
        "bolt://unused",
        "neo4j",
        "secret",
        "neo4j",
        driver=FakeDriver(handler),
        verify_connectivity=False,
    )

    assert repository.list_requirements()[0].id == "REQ-001"
    assert repository.list_components()[0].id == "CMP-001"
    assert repository.list_risks()[0].id == "RSK-001"
    assert repository.list_test_cases()[0].id == "TST-001"
    assert repository.transitive_dependencies("REQ-002", 2)[0].id == "REQ-001"
    assert repository.downstream_impact("REQ-001", 2)[0].id == "REQ-001"
    assert repository.components_for_requirement("REQ-001")[0].id == "CMP-001"
    assert repository.requirements_for_component("CMP-001")[0].id == "REQ-001"
    assert repository.shortest_path("TST-001", "REQ-001") is not None
    assert repository.shortest_path("REQ-001", "REQ-001") is not None
    assert repository.dependency_cycles() == [["REQ-001", "REQ-002", "REQ-001"]]
    assert repository.unverified_risks()[0].id == "RSK-001"
    assert repository.orphan_nodes()[0].id == "CMP-999"


def test_shortest_path_returns_none_when_unconnected() -> None:
    driver = FakeDriver(
        lambda query, _parameters: [{"path": None}] if query == SHORTEST_PATH_QUERY else []
    )
    repository = Neo4jRepository(
        "bolt://unused", "neo4j", "secret", "neo4j", driver=driver, verify_connectivity=False
    )

    assert repository.shortest_path("REQ-001", "RSK-999") is None
    assert repository.shortest_path("REQ-999", "REQ-999") is None


def test_graph_counts_include_explicit_zero_values() -> None:
    driver = FakeDriver(
        lambda query, _parameters: (
            [{"node_pairs": [], "relationship_pairs": []}] if query == GRAPH_COUNTS_QUERY else []
        )
    )
    repository = Neo4jRepository(
        "bolt://unused", "neo4j", "secret", "neo4j", driver=driver, verify_connectivity=False
    )

    counts = repository.graph_counts()

    assert set(counts.nodes.values()) == {0}
    assert set(counts.relationships.values()) == {0}


@pytest.mark.parametrize("reset", [False, True])
def test_seeding_uses_merge_and_only_resets_explicitly(reset: bool) -> None:
    dataset: Dataset = load_dataset(DATA_FILE)
    driver = FakeDriver(
        lambda query, _parameters: [graph_count_record()] if query == GRAPH_COUNTS_QUERY else []
    )
    repository = Neo4jRepository(
        "bolt://unused", "neo4j", "secret", "neo4j", driver=driver, verify_connectivity=False
    )

    counts = repository.seed_dataset(dataset, reset=reset)

    queries = [call["query"] for call in driver.calls]
    assert ("MATCH (node) DETACH DELETE node" in queries) is reset
    assert sum("MERGE (" in query for query in queries) == 8
    assert all(call["database_"] == "neo4j" for call in driver.calls)
    assert counts.relationships == {
        "DEPENDS_ON": 13,
        "APPLIES_TO": 39,
        "ADDRESSES": 18,
        "VERIFIES": 12,
    }
    requirement_call = next(
        call for call in driver.calls if "MERGE (node:Requirement" in call["query"]
    )
    assert "component_ids" not in requirement_call["parameters_"]["rows"][0]


def test_connection_failures_are_translated() -> None:
    repository = Neo4jRepository(
        "bolt://unused",
        "neo4j",
        "secret",
        "neo4j",
        driver=FakeDriver(error=ServiceUnavailable("offline")),
        verify_connectivity=False,
    )

    with pytest.raises(RepositoryConnectionError, match="unable to connect"):
        repository.verify_connectivity()


def test_query_failures_are_translated() -> None:
    repository = Neo4jRepository(
        "bolt://unused",
        "neo4j",
        "secret",
        "neo4j",
        driver=FakeDriver(error=Neo4jError("invalid query")),
        verify_connectivity=False,
    )

    with pytest.raises(RepositoryQueryError, match="operation failed"):
        repository.list_components()


def test_owned_driver_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = FakeDriver(lambda _query, _parameters: [{"ok": 1}])
    monkeypatch.setattr(GraphDatabase, "driver", lambda *_args, **_kwargs: driver)
    repository = Neo4jRepository("bolt://unused", "neo4j", "secret", "neo4j")

    repository.close()

    assert driver.closed is True


def test_driver_configuration_failure_is_translated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise ConfigurationError("unsupported URI")

    monkeypatch.setattr(GraphDatabase, "driver", fail)

    with pytest.raises(RepositoryConnectionError, match="configure the Neo4j driver"):
        Neo4jRepository("invalid://host", "neo4j", "secret", "neo4j")


def test_owned_driver_closes_when_connectivity_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = FakeDriver()
    monkeypatch.setattr(GraphDatabase, "driver", lambda *_args, **_kwargs: driver)

    with pytest.raises(RepositoryConnectionError, match="returned no result"):
        Neo4jRepository("bolt://unused", "neo4j", "secret", "neo4j")

    assert driver.closed is True
