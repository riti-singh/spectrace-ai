"""Isolated Neo4j 5.26 integration and backend-parity tests."""

import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from neo4j import Driver, GraphDatabase, RoutingControl
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from app.models import RetrievalRequest
from app.repositories import JsonDataRepository, Neo4jRepository, load_dataset
from app.retrieval.evaluation import EvaluationDataset
from app.retrieval.report import build_report
from app.services.graph import GraphTraversalService
from app.services.retrieval import RetrievalService
from app.services.traceability import TraceabilityService
from scripts.evaluate_retrieval import load_evaluation
from tests.conftest import DATA_FILE
from tests.repository_contract import assert_asteria_repository_contract

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Neo4jTestContext:
    repository: Neo4jRepository
    driver: Driver
    database: str
    uri: str
    username: str
    password: str

    def execute(self, query: str, parameters: Mapping[str, Any] | None = None) -> None:
        self.driver.execute_query(
            query,
            parameters_=parameters or {},
            routing_=RoutingControl.WRITE,
            database_=self.database,
        )


@pytest.fixture(scope="module")
def neo4j_context() -> Iterator[Neo4jTestContext]:
    if os.getenv("SPECTRACE_RUN_NEO4J_TESTS") != "1":
        pytest.skip("set SPECTRACE_RUN_NEO4J_TESTS=1 to run Neo4j integration tests")
    if os.getenv("SPECTRACE_NEO4J_TEST_ISOLATED") != "1":
        pytest.fail("Neo4j tests require explicit confirmation of an isolated disposable database")

    uri = os.environ["SPECTRACE_NEO4J_TEST_URI"]
    username = os.environ["SPECTRACE_NEO4J_TEST_USERNAME"]
    password = os.environ["SPECTRACE_NEO4J_TEST_PASSWORD"]
    database = os.getenv("SPECTRACE_NEO4J_TEST_DATABASE", "neo4j")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    repository = Neo4jRepository(
        uri,
        username,
        password,
        database,
        driver=driver,
    )
    repository.seed_dataset(load_dataset(DATA_FILE), reset=True)
    context = Neo4jTestContext(repository, driver, database, uri, username, password)
    try:
        yield context
    finally:
        repository.reset_graph()
        driver.close()


def test_seed_is_idempotent_and_counts_are_exact(neo4j_context: Neo4jTestContext) -> None:
    dataset = load_dataset(DATA_FILE)

    first = neo4j_context.repository.seed_dataset(dataset)
    second = neo4j_context.repository.seed_dataset(dataset)

    assert first == second
    assert first.nodes == {
        "Requirement": 16,
        "Component": 7,
        "Risk": 7,
        "TestCase": 9,
    }
    assert first.relationships == {
        "DEPENDS_ON": 13,
        "APPLIES_TO": 39,
        "ADDRESSES": 18,
        "VERIFIES": 12,
    }


def test_neo4j_repository_satisfies_shared_contract(
    neo4j_context: Neo4jTestContext,
) -> None:
    assert_asteria_repository_contract(neo4j_context.repository)


def test_traceability_outputs_match_json_backend(
    neo4j_context: Neo4jTestContext,
) -> None:
    json_service = TraceabilityService(JsonDataRepository(DATA_FILE))
    graph_service = TraceabilityService(neo4j_context.repository)

    assert graph_service.get_summary() == json_service.get_summary()
    for number in range(1, 17):
        requirement_id = f"REQ-{number:03d}"
        assert graph_service.get_requirement_traceability(
            requirement_id
        ) == json_service.get_requirement_traceability(requirement_id)


def test_transitive_depth_and_downstream_impact(
    neo4j_context: Neo4jTestContext,
) -> None:
    service = GraphTraversalService(neo4j_context.repository)

    assert [item.id for item in service.dependencies("REQ-011", 1).requirements] == ["REQ-002"]
    assert [item.id for item in service.dependencies("REQ-011", 2).requirements] == [
        "REQ-001",
        "REQ-002",
    ]
    assert [item.id for item in service.impact("REQ-001", 1).requirements] == [
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-015",
    ]
    assert [item.id for item in service.impact("REQ-001", 2).requirements] == [
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-007",
        "REQ-011",
        "REQ-013",
        "REQ-015",
        "REQ-016",
    ]
    assert [item.id for item in service.requirements_for_component("CMP-001")] == [
        "REQ-001",
        "REQ-003",
        "REQ-004",
        "REQ-014",
    ]


def test_shortest_traceability_path(neo4j_context: Neo4jTestContext) -> None:
    service = GraphTraversalService(neo4j_context.repository)

    path = service.shortest_path("TST-003", "RSK-002")
    identity_path = service.shortest_path("REQ-001", "REQ-001")

    assert [node.id for node in path.nodes] == ["TST-003", "REQ-003", "RSK-002"]
    assert path.relationship_types == ["VERIFIES", "ADDRESSES"]
    assert [node.id for node in identity_path.nodes] == ["REQ-001"]
    assert identity_path.relationship_types == []


def test_cycle_detection_with_isolated_fixture(neo4j_context: Neo4jTestContext) -> None:
    neo4j_context.execute(
        "MATCH (source:Requirement {id: $source_id}) "
        "MATCH (target:Requirement {id: $target_id}) "
        "MERGE (source)-[:DEPENDS_ON]->(target)",
        {"source_id": "REQ-001", "target_id": "REQ-003"},
    )
    try:
        cycles = GraphTraversalService(neo4j_context.repository).cycles()
        assert any({"REQ-001", "REQ-003"}.issubset(cycle.requirement_ids) for cycle in cycles)
    finally:
        neo4j_context.execute(
            "MATCH (:Requirement {id: $source_id})-[edge:DEPENDS_ON]->"
            "(:Requirement {id: $target_id}) DELETE edge",
            {"source_id": "REQ-001", "target_id": "REQ-003"},
        )


def test_orphan_and_unverified_risk_detection(neo4j_context: Neo4jTestContext) -> None:
    neo4j_context.execute(
        "CREATE (:Component {id: $id, name: $name, description: $description})",
        {
            "id": "CMP-999",
            "name": "Isolated fixture component",
            "description": "Disposable integration-test orphan node.",
        },
    )
    neo4j_context.execute(
        "MATCH (requirement:Requirement {id: $requirement_id}) "
        "CREATE (risk:Risk {id: $risk_id, title: $title, description: $description, "
        "severity: $severity, mitigation: $mitigation}) "
        "CREATE (requirement)-[:ADDRESSES]->(risk)",
        {
            "requirement_id": "REQ-008",
            "risk_id": "RSK-999",
            "title": "Unverified fixture risk",
            "description": "Disposable integration risk without a verifying test path.",
            "severity": "high",
            "mitigation": "Remove the disposable fixture after the assertion.",
        },
    )
    try:
        service = GraphTraversalService(neo4j_context.repository)
        assert "CMP-999" in {node.id for node in service.orphans()}
        assert "RSK-999" in {risk.id for risk in service.unverified_risks()}
    finally:
        neo4j_context.execute(
            "MATCH (node) WHERE node.id IN $ids DETACH DELETE node",
            {"ids": ["CMP-999", "RSK-999"]},
        )


def test_existing_api_traceability_parity(neo4j_context: Neo4jTestContext) -> None:
    json_app = create_app(Settings(_env_file=None, repository_backend="json", data_file=DATA_FILE))
    neo4j_app = create_app(
        Settings(
            _env_file=None,
            repository_backend="neo4j",
            neo4j_uri=neo4j_context.uri,
            neo4j_username=neo4j_context.username,
            neo4j_password=SecretStr(neo4j_context.password),
            neo4j_database=neo4j_context.database,
        )
    )
    with TestClient(json_app) as json_client, TestClient(neo4j_app) as neo4j_client:
        paths = ["/traceability/summary", "/traceability/uncovered"] + [
            f"/traceability/requirements/REQ-{number:03d}" for number in range(1, 17)
        ]
        for path in paths:
            assert neo4j_client.get(path).json() == json_client.get(path).json()


def test_native_hybrid_retrieval_and_bounded_filters(
    neo4j_context: Neo4jTestContext,
) -> None:
    service = RetrievalService(neo4j_context.repository)

    response = service.search(
        RetrievalRequest.model_validate(
            {
                "query": "thermal temperature shutdown protection",
                "entity_types": ["Requirement", "TestCase", "Risk"],
                "relationships": ["VERIFIES", "ADDRESSES", "DEPENDS_ON"],
                "result_count": 5,
                "graph_depth": 2,
            }
        )
    )

    assert response.result_count == 5
    assert "REQ-006" in {item.id for item in response.results}
    assert all(item.entity_type.value != "Component" for item in response.results)
    assert all(item.explanation.fusion_method.endswith("k_10") for item in response.results)
    assert any(item.explanation.graph is not None for item in response.results)


def test_retrieval_api_matches_service(neo4j_context: Neo4jTestContext) -> None:
    application = create_app(
        Settings(
            _env_file=None,
            repository_backend="neo4j",
            neo4j_uri=neo4j_context.uri,
            neo4j_username=neo4j_context.username,
            neo4j_password=SecretStr(neo4j_context.password),
            neo4j_database=neo4j_context.database,
        )
    )
    payload = {
        "query": "tampered firmware image recovery",
        "mode": "hybrid",
        "entity_types": ["Requirement", "TestCase", "Risk"],
        "result_count": 4,
    }
    with TestClient(application) as client:
        first = client.post("/retrieval/search", json=payload)
        second = client.post("/retrieval/search", json=payload)

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["result_count"] == 4


def test_checked_in_evaluation_runs_all_modes(neo4j_context: Neo4jTestContext) -> None:
    dataset: EvaluationDataset = load_evaluation(DATA_FILE.parent / "retrieval_evaluation.json")

    service = RetrievalService(neo4j_context.repository)
    report = build_report(service.search, dataset, measure_latency=False)

    measured = {
        strategy.mode.value: strategy.metrics.model_dump() for strategy in report.strategies
    }
    assert set(measured) == {"lexical", "semantic", "graph", "hybrid"}
    assert (
        report.model_dump_json()
        == build_report(service.search, dataset, measure_latency=False).model_dump_json()
    )
    expected = {
        "lexical": {
            "precision_at_k": 0.6,
            "recall_at_k": 0.7625,
            "mrr": 0.875,
            "ndcg_at_k": 0.8232410371676033,
        },
        "semantic": {
            "precision_at_k": 0.625,
            "recall_at_k": 0.7669642857142858,
            "mrr": 1.0,
            "ndcg_at_k": 0.8523920015313283,
        },
        "graph": {
            "precision_at_k": 0.225,
            "recall_at_k": 0.22857142857142856,
            "mrr": 0.5,
            "ndcg_at_k": 0.15302846884465263,
        },
        "hybrid": {
            "precision_at_k": 0.65,
            "recall_at_k": 0.7982142857142858,
            "mrr": 0.9375,
            "ndcg_at_k": 0.8424440621028894,
        },
    }
    for mode, metrics in expected.items():
        assert measured[mode] == pytest.approx(metrics)
    assert report.failure_analysis.findings
