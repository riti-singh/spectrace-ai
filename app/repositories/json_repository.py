"""Validated JSON-backed implementation of the domain repository."""

import json
import math
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models import (
    Component,
    Dataset,
    GraphEntityType,
    Requirement,
    RetrievalCandidate,
    Risk,
    TestCase,
)
from app.repositories.exceptions import DatasetLoadError
from app.retrieval import EMBEDDING_DIMENSIONS, DeterministicSemanticEncoder
from app.retrieval.embedding import entity_search_document

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def load_dataset(data_file: Path) -> Dataset:
    """Load a JSON dataset and enforce complete Pydantic and reference validation."""

    try:
        raw_data = json.loads(data_file.read_text(encoding="utf-8"))
        return Dataset.model_validate(raw_data)
    except FileNotFoundError as exc:
        raise DatasetLoadError(f"dataset file not found: {data_file}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetLoadError(
            f"dataset contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except ValidationError as exc:
        raise DatasetLoadError(f"dataset integrity validation failed: {exc}") from exc


class JsonDataRepository:
    """Load and serve an immutable snapshot of a JSON domain dataset."""

    def __init__(self, data_file: Path) -> None:
        self._data_file = data_file
        self._dataset = load_dataset(data_file)
        self._requirements_by_id = {item.id: item for item in self._dataset.requirements}
        self._encoder = DeterministicSemanticEncoder()
        self._search_records = self._build_search_records()
        self._adjacency = self._build_adjacency()

    def list_requirements(self) -> list[Requirement]:
        return sorted(self._dataset.requirements, key=lambda item: item.id)

    def get_requirement(self, requirement_id: str) -> Requirement | None:
        return self._requirements_by_id.get(requirement_id)

    def list_components(self) -> list[Component]:
        return sorted(self._dataset.components, key=lambda item: item.id)

    def list_risks(self) -> list[Risk]:
        return sorted(self._dataset.risks, key=lambda item: item.id)

    def list_test_cases(self) -> list[TestCase]:
        return sorted(self._dataset.test_cases, key=lambda item: item.id)

    def lexical_candidates(
        self, query: str, entity_types: list[str], limit: int
    ) -> list[RetrievalCandidate]:
        query_tokens = _TOKEN_PATTERN.findall(query.lower())
        if not query_tokens:
            return []
        allowed = set(entity_types)
        candidates: list[RetrievalCandidate] = []
        for record in self._search_records.values():
            if record["entity_type"] not in allowed:
                continue
            document_tokens = _TOKEN_PATTERN.findall(record["document"].lower())
            score = sum(
                document_token == query_token
                for query_token in query_tokens
                for document_token in document_tokens
            )
            if score:
                candidates.append(self._candidate(record, float(score)))
        return sorted(candidates, key=lambda item: (-item.raw_score, item.id))[:limit]

    def semantic_candidates(
        self, embedding: list[float], entity_types: list[str], limit: int
    ) -> list[RetrievalCandidate]:
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"embedding must contain {EMBEDDING_DIMENSIONS} values")
        if not any(embedding):
            return []
        allowed = set(entity_types)
        candidates: list[RetrievalCandidate] = []
        for record in self._search_records.values():
            if record["entity_type"] not in allowed:
                continue
            score = math.fsum(
                left * right for left, right in zip(embedding, record["embedding"], strict=True)
            )
            if score > 0.0:
                candidates.append(self._candidate(record, score))
        return sorted(candidates, key=lambda item: (-item.raw_score, item.id))[:limit]

    def graph_candidates(
        self,
        seed_ids: list[str],
        entity_types: list[str],
        relationships: list[str],
        depth: int,
        limit: int,
    ) -> list[RetrievalCandidate]:
        allowed_types = set(entity_types)
        allowed_relationships = set(relationships)
        seed_set = set(seed_ids)
        distances: dict[str, int] = {}
        anchors: dict[str, set[str]] = defaultdict(set)
        for seed_id in seed_ids:
            if seed_id not in self._search_records:
                continue
            queue = deque([(seed_id, 0)])
            visited = {seed_id}
            while queue:
                node_id, distance = queue.popleft()
                if distance >= depth:
                    continue
                for neighbor_id, relationship in self._adjacency[node_id]:
                    if relationship not in allowed_relationships or neighbor_id in visited:
                        continue
                    visited.add(neighbor_id)
                    next_distance = distance + 1
                    queue.append((neighbor_id, next_distance))
                    record = self._search_records[neighbor_id]
                    if neighbor_id not in seed_set and record["entity_type"] in allowed_types:
                        distances[neighbor_id] = min(
                            distances.get(neighbor_id, depth + 1), next_distance
                        )
                        anchors[neighbor_id].add(seed_id)
        candidates = [
            self._candidate(
                self._search_records[entity_id],
                1.0 / distance,
                graph_distance=distance,
                anchor_ids=sorted(anchors[entity_id]),
            )
            for entity_id, distance in distances.items()
        ]
        return sorted(candidates, key=lambda item: (item.graph_distance or 0, item.id))[:limit]

    def _build_search_records(self) -> dict[str, dict[str, Any]]:
        typed_entities = (
            *((item, GraphEntityType.REQUIREMENT) for item in self._dataset.requirements),
            *((item, GraphEntityType.COMPONENT) for item in self._dataset.components),
            *((item, GraphEntityType.RISK) for item in self._dataset.risks),
            *((item, GraphEntityType.TEST_CASE) for item in self._dataset.test_cases),
        )
        records: dict[str, dict[str, Any]] = {}
        for entity, entity_type in typed_entities:
            document = entity_search_document(entity)
            records[entity.id] = {
                "id": entity.id,
                "entity_type": entity_type.value,
                "title": getattr(entity, "title", getattr(entity, "name", entity.id)),
                "text": getattr(
                    entity,
                    "normative_text",
                    getattr(entity, "description", getattr(entity, "objective", "")),
                ),
                "document": document,
                "embedding": self._encoder.encode(document),
            }
        return records

    def _build_adjacency(self) -> dict[str, list[tuple[str, str]]]:
        adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
        edges: list[tuple[str, str, str]] = []
        for requirement in self._dataset.requirements:
            edges.extend(
                (requirement.id, target, "DEPENDS_ON") for target in requirement.dependency_ids
            )
            edges.extend(
                (requirement.id, target, "APPLIES_TO") for target in requirement.component_ids
            )
            edges.extend((requirement.id, target, "ADDRESSES") for target in requirement.risk_ids)
        for test_case in self._dataset.test_cases:
            edges.extend((test_case.id, target, "VERIFIES") for target in test_case.requirement_ids)
        for source, target, relationship in edges:
            adjacency[source].append((target, relationship))
            adjacency[target].append((source, relationship))
        return adjacency

    @staticmethod
    def _candidate(
        record: dict[str, Any],
        raw_score: float,
        *,
        graph_distance: int | None = None,
        anchor_ids: list[str] | None = None,
    ) -> RetrievalCandidate:
        return RetrievalCandidate(
            id=record["id"],
            entity_type=record["entity_type"],
            title=record["title"],
            text=record["text"],
            raw_score=raw_score,
            graph_distance=graph_distance,
            anchor_ids=anchor_ids or [],
        )

    def close(self) -> None:
        """Satisfy the repository lifecycle contract; JSON holds no external resources."""
