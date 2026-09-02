from typing import Any

import pytest

from app.models import RetrievalCandidate, RetrievalMode, RetrievalRequest
from app.services.retrieval import RetrievalService


def candidate(
    entity_id: str,
    score: float,
    *,
    entity_type: str = "Requirement",
    distance: int | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate.model_validate(
        {
            "id": entity_id,
            "entity_type": entity_type,
            "title": entity_id,
            "text": f"Text for {entity_id}",
            "raw_score": score,
            "graph_distance": distance,
            "anchor_ids": ["REQ-002"] if distance else [],
        }
    )


class FakeRetrievalRepository:
    def __init__(self) -> None:
        self.lexical = [candidate("REQ-001", 8.0), candidate("REQ-002", 4.0)]
        self.semantic = [candidate("REQ-002", 0.9), candidate("REQ-003", 0.8)]
        self.graph = [candidate("REQ-003", 1.0, distance=1)]
        self.calls: list[tuple[str, Any]] = []

    def lexical_candidates(self, query: str, entity_types: list[str], limit: int):
        self.calls.append(("lexical", (query, entity_types, limit)))
        return self.lexical

    def semantic_candidates(self, embedding: list[float], entity_types: list[str], limit: int):
        self.calls.append(("semantic", (len(embedding), entity_types, limit)))
        return self.semantic

    def graph_candidates(
        self,
        seed_ids: list[str],
        entity_types: list[str],
        relationships: list[str],
        depth: int,
        limit: int,
    ):
        self.calls.append(("graph", (seed_ids, entity_types, relationships, depth, limit)))
        return self.graph


def test_hybrid_fusion_is_deterministic_and_explainable() -> None:
    repository = FakeRetrievalRepository()
    service = RetrievalService(repository)  # type: ignore[arg-type]

    first = service.search(RetrievalRequest(query="req-002 authentication", result_count=3))
    second = service.search(RetrievalRequest(query="req-002 authentication", result_count=3))

    assert first == second
    assert [item.id for item in first.results] == ["REQ-002", "REQ-003", "REQ-001"]
    req_003 = first.results[1]
    assert req_003.explanation.semantic is not None
    assert req_003.explanation.graph is not None
    assert req_003.explanation.graph_distance == 1
    assert req_003.explanation.anchor_ids == ["REQ-002"]
    graph_call = next(value for name, value in repository.calls if name == "graph")
    assert graph_call[0][0] == "REQ-002"
    assert graph_call[3] == 2


@pytest.mark.parametrize("mode", list(RetrievalMode))
def test_each_mode_returns_only_its_selected_components(mode: RetrievalMode) -> None:
    repository = FakeRetrievalRepository()
    response = RetrievalService(repository).search(  # type: ignore[arg-type]
        RetrievalRequest(query="thermal", mode=mode, result_count=3)
    )

    for result in response.results:
        populated = {
            name
            for name in ("lexical", "semantic", "graph")
            if getattr(result.explanation, name) is not None
        }
        if mode is RetrievalMode.HYBRID:
            assert populated
        else:
            assert populated == {mode.value}


def test_empty_graph_seeds_produce_empty_graph_results() -> None:
    repository = FakeRetrievalRepository()
    repository.lexical = []
    repository.semantic = []
    repository.graph = []

    response = RetrievalService(repository).search(  # type: ignore[arg-type]
        RetrievalRequest(query="unknown", mode="graph")
    )

    assert response.results == []
