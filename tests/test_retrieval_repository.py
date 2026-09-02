import pytest

from app.repositories import Neo4jRepository
from app.repositories.neo4j_repository import (
    GRAPH_CANDIDATES_QUERY,
    LEXICAL_CANDIDATES_QUERY,
    SEMANTIC_CANDIDATES_QUERY,
)
from app.retrieval import EMBEDDING_DIMENSIONS
from tests.fakes import FakeDriver


def candidate_record(score: float = 0.75) -> dict[str, object]:
    return {
        "candidate": {
            "id": "REQ-005",
            "entity_type": "Requirement",
            "title": "Thermal transmit-power protection",
            "text": "The terminal shall reduce RF transmit power.",
            "raw_score": score,
        }
    }


def test_lexical_query_uses_sanitized_tokens_and_bounded_parameters() -> None:
    driver = FakeDriver(
        lambda query, _: [candidate_record()] if query == LEXICAL_CANDIDATES_QUERY else []
    )
    repository = Neo4jRepository(
        "bolt://unused", "neo4j", "secret", "neo4j", driver=driver, verify_connectivity=False
    )

    results = repository.lexical_candidates("thermal +(shutdown):*", ["Requirement"], 7)

    assert [item.id for item in results] == ["REQ-005"]
    call = driver.calls[-1]
    assert call["parameters_"]["query"] == '"thermal" OR "shutdown"'
    assert call["parameters_"]["candidate_limit"] == 28
    assert call["parameters_"]["limit"] == 7
    assert repository.lexical_candidates("+++", ["Requirement"], 7) == []


def test_semantic_query_validates_dimensions() -> None:
    driver = FakeDriver(
        lambda query, _: [candidate_record(0.9)] if query == SEMANTIC_CANDIDATES_QUERY else []
    )
    repository = Neo4jRepository(
        "bolt://unused", "neo4j", "secret", "neo4j", driver=driver, verify_connectivity=False
    )

    results = repository.semantic_candidates([0.0] * EMBEDDING_DIMENSIONS, ["Requirement"], 25)

    assert results[0].raw_score == 0.9
    assert driver.calls[-1]["parameters_"]["candidate_limit"] == 100
    with pytest.raises(ValueError, match="256"):
        repository.semantic_candidates([0.0], ["Requirement"], 5)


def test_graph_query_preserves_bounded_filter_parameters() -> None:
    record = candidate_record(1.0)
    record["candidate"]["graph_distance"] = 1  # type: ignore[index]
    record["candidate"]["anchor_ids"] = ["REQ-006", "REQ-005"]  # type: ignore[index]
    driver = FakeDriver(lambda query, _: [record] if query == GRAPH_CANDIDATES_QUERY else [])
    repository = Neo4jRepository(
        "bolt://unused", "neo4j", "secret", "neo4j", driver=driver, verify_connectivity=False
    )

    results = repository.graph_candidates(["REQ-005"], ["Risk"], ["ADDRESSES"], depth=2, limit=4)

    assert results[0].graph_distance == 1
    assert driver.calls[-1]["parameters_"] == {
        "seed_ids": ["REQ-005"],
        "entity_types": ["Risk"],
        "relationships": ["ADDRESSES"],
        "depth": 2,
        "limit": 4,
    }
    assert repository.graph_candidates([], ["Risk"], ["ADDRESSES"], 2, 4) == []
