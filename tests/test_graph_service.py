"""Bounded graph traversal service tests."""

from unittest.mock import Mock

import pytest

from app.models import GraphNode, GraphPath
from app.repositories import JsonDataRepository
from app.services.graph import (
    GraphTraversalService,
    InvalidTraversalDepthError,
    TraceabilityPathNotFoundError,
)
from app.services.traceability import RequirementNotFoundError
from tests.conftest import DATA_FILE


@pytest.fixture
def graph_repository() -> Mock:
    source = JsonDataRepository(DATA_FILE)
    repository = Mock()
    repository.database = "spectrace-test"
    repository.get_requirement.side_effect = source.get_requirement
    repository.transitive_dependencies.return_value = [
        source.get_requirement("REQ-001"),
        source.get_requirement("REQ-002"),
    ]
    repository.downstream_impact.return_value = [source.get_requirement("REQ-003")]
    repository.components_for_requirement.return_value = source.list_components()[:2]
    repository.requirements_for_component.return_value = source.list_requirements()[:2]
    repository.shortest_path.return_value = GraphPath(
        nodes=[
            GraphNode(id="TST-001", entity_type="TestCase"),
            GraphNode(id="REQ-001", entity_type="Requirement"),
        ],
        relationship_types=["VERIFIES"],
    )
    repository.dependency_cycles.return_value = [
        ["REQ-003", "REQ-001", "REQ-002", "REQ-003"],
        ["REQ-001", "REQ-002", "REQ-003", "REQ-001"],
    ]
    repository.unverified_risks.return_value = source.list_risks()[:1]
    repository.orphan_nodes.return_value = [GraphNode(id="CMP-007", entity_type="Component")]
    return repository


@pytest.fixture
def graph_service(graph_repository: Mock) -> GraphTraversalService:
    return GraphTraversalService(graph_repository)


def test_health_verifies_connectivity(
    graph_service: GraphTraversalService, graph_repository: Mock
) -> None:
    health = graph_service.health()

    assert health.model_dump() == {
        "status": "ok",
        "backend": "neo4j",
        "database": "spectrace-test",
    }
    graph_repository.verify_connectivity.assert_called_once_with()


def test_dependency_and_impact_depth_is_forwarded(
    graph_service: GraphTraversalService, graph_repository: Mock
) -> None:
    dependencies = graph_service.dependencies("REQ-003", 2)
    impact = graph_service.impact("REQ-001", 4)

    assert [item.id for item in dependencies.requirements] == ["REQ-001", "REQ-002"]
    assert dependencies.depth == 2
    assert [item.id for item in impact.requirements] == ["REQ-003"]
    graph_repository.transitive_dependencies.assert_called_once_with("REQ-003", 2)
    graph_repository.downstream_impact.assert_called_once_with("REQ-001", 4)


@pytest.mark.parametrize("depth", [0, 11, -1, 100])
def test_invalid_depth_is_rejected(graph_service: GraphTraversalService, depth: int) -> None:
    with pytest.raises(InvalidTraversalDepthError, match="between 1 and 10"):
        graph_service.dependencies("REQ-003", depth)


def test_missing_requirement_is_distinct_from_empty_results(
    graph_service: GraphTraversalService,
) -> None:
    with pytest.raises(RequirementNotFoundError):
        graph_service.components("REQ-999")


def test_component_traversals(graph_service: GraphTraversalService) -> None:
    assert [item.id for item in graph_service.components("REQ-001")] == [
        "CMP-001",
        "CMP-002",
    ]
    assert [item.id for item in graph_service.requirements_for_component("CMP-001")] == [
        "REQ-001",
        "REQ-002",
    ]


def test_shortest_path_and_missing_path(
    graph_service: GraphTraversalService, graph_repository: Mock
) -> None:
    path = graph_service.shortest_path("TST-001", "REQ-001")

    assert path.relationship_types == ["VERIFIES"]
    graph_repository.shortest_path.return_value = None
    with pytest.raises(TraceabilityPathNotFoundError):
        graph_service.shortest_path("TST-001", "RSK-007")


def test_cycles_are_canonicalized_and_deduplicated(
    graph_service: GraphTraversalService,
) -> None:
    cycles = graph_service.cycles()

    assert [cycle.requirement_ids for cycle in cycles] == [
        ["REQ-001", "REQ-002", "REQ-003", "REQ-001"]
    ]


def test_empty_cycle_records_are_ignored(
    graph_service: GraphTraversalService, graph_repository: Mock
) -> None:
    graph_repository.dependency_cycles.return_value = [[]]

    assert graph_service.cycles() == []


def test_risk_and_orphan_results(graph_service: GraphTraversalService) -> None:
    assert [risk.id for risk in graph_service.unverified_risks()] == ["RSK-001"]
    assert [node.id for node in graph_service.orphans()] == ["CMP-007"]
