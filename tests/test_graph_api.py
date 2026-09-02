"""Graph endpoint contracts for backend gating, validation, and successful responses."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_graph_service, get_repository
from app.main import create_app
from app.models import (
    DependencyCycle,
    DependencyTraversal,
    GraphHealth,
    GraphNode,
    GraphPath,
    Requirement,
)
from app.repositories import JsonDataRepository, RepositoryQueryError
from app.services.graph import TraceabilityPathNotFoundError
from app.services.traceability import RequirementNotFoundError
from tests.conftest import DATA_FILE

GRAPH_ENDPOINTS = [
    "/graph/health",
    "/graph/requirements/REQ-003/dependencies",
    "/graph/requirements/REQ-001/impact",
    "/graph/requirements/REQ-003/components",
    "/graph/path?source_id=TST-003&target_id=RSK-002",
    "/graph/cycles",
    "/graph/risks/unverified",
    "/graph/orphans",
]


def test_graph_endpoints_require_neo4j_backend(client: TestClient) -> None:
    for path in GRAPH_ENDPOINTS:
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "neo4j_backend_required"


@pytest.fixture
def graph_api() -> tuple[TestClient, Mock]:
    source = JsonDataRepository(DATA_FILE)
    requirement = source.get_requirement("REQ-003")
    assert requirement is not None
    service = Mock()
    service.health.return_value = GraphHealth(status="ok", backend="neo4j", database="neo4j")
    service.dependencies.return_value = DependencyTraversal(
        requirement_id="REQ-003", depth=2, requirements=[requirement]
    )
    service.impact.return_value = DependencyTraversal(
        requirement_id="REQ-001", depth=2, requirements=[requirement]
    )
    service.components.return_value = source.list_components()[:1]
    service.shortest_path.return_value = GraphPath(
        nodes=[
            GraphNode(id="TST-003", entity_type="TestCase"),
            GraphNode(id="REQ-003", entity_type="Requirement"),
            GraphNode(id="RSK-002", entity_type="Risk"),
        ],
        relationship_types=["VERIFIES", "ADDRESSES"],
    )
    service.cycles.return_value = [
        DependencyCycle(requirement_ids=["REQ-001", "REQ-002", "REQ-001"])
    ]
    service.unverified_risks.return_value = source.list_risks()[:1]
    service.orphans.return_value = [GraphNode(id="CMP-007", entity_type="Component")]
    application = create_app(Settings(_env_file=None, data_file=DATA_FILE))
    application.dependency_overrides[get_graph_service] = lambda: service
    return TestClient(application), service


def test_all_graph_endpoints_return_typed_results(
    graph_api: tuple[TestClient, Mock],
) -> None:
    client, _ = graph_api
    expected = {
        "/graph/health": ("database", "neo4j"),
        "/graph/requirements/REQ-003/dependencies?depth=2": ("depth", 2),
        "/graph/requirements/REQ-001/impact?depth=2": ("depth", 2),
        "/graph/requirements/REQ-003/components": ("id", "CMP-001"),
        "/graph/path?source_id=TST-003&target_id=RSK-002": (
            "relationship_types",
            ["VERIFIES", "ADDRESSES"],
        ),
        "/graph/cycles": ("requirement_ids", ["REQ-001", "REQ-002", "REQ-001"]),
        "/graph/risks/unverified": ("id", "RSK-001"),
        "/graph/orphans": ("id", "CMP-007"),
    }
    for path, (field, value) in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        target = payload[0] if isinstance(payload, list) else payload
        assert target[field] == value


@pytest.mark.parametrize("depth", [0, 11])
def test_graph_depth_validation(graph_api: tuple[TestClient, Mock], depth: int) -> None:
    client, _ = graph_api

    response = client.get(f"/graph/requirements/REQ-003/dependencies?depth={depth}")

    assert response.status_code == 422


def test_graph_requirement_not_found(graph_api: tuple[TestClient, Mock]) -> None:
    client, service = graph_api
    service.dependencies.side_effect = RequirementNotFoundError("REQ-999")

    response = client.get("/graph/requirements/REQ-999/dependencies")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "requirement_not_found"


@pytest.mark.parametrize(
    ("method_name", "path"),
    [
        ("impact", "/graph/requirements/REQ-999/impact"),
        ("components", "/graph/requirements/REQ-999/components"),
    ],
)
def test_other_graph_requirement_routes_report_missing_ids(
    graph_api: tuple[TestClient, Mock], method_name: str, path: str
) -> None:
    client, service = graph_api
    getattr(service, method_name).side_effect = RequirementNotFoundError("REQ-999")

    response = client.get(path)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "requirement_not_found"


def test_graph_path_not_found(graph_api: tuple[TestClient, Mock]) -> None:
    client, service = graph_api
    service.shortest_path.side_effect = TraceabilityPathNotFoundError("missing")

    response = client.get("/graph/path?source_id=REQ-001&target_id=RSK-999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "traceability_path_not_found"


def test_graph_entity_id_validation(graph_api: tuple[TestClient, Mock]) -> None:
    client, _ = graph_api

    response = client.get("/graph/path?source_id=invalid&target_id=REQ-001")

    assert response.status_code == 422


def test_repository_query_error_is_safely_translated() -> None:
    class BrokenRepository(JsonDataRepository):
        def list_requirements(self) -> list[Requirement]:
            raise RepositoryQueryError("driver details must not escape")

    application = create_app(Settings(_env_file=None, data_file=DATA_FILE))
    application.dependency_overrides[get_repository] = lambda: BrokenRepository(DATA_FILE)

    with TestClient(application) as client:
        response = client.get("/requirements")

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "code": "repository_operation_failed",
        "message": "The persistence backend could not complete the operation.",
    }
