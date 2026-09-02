"""Repository contracts used by services and API dependencies."""

from typing import Protocol, runtime_checkable

from app.models import (
    Component,
    GraphNode,
    GraphPath,
    Requirement,
    RetrievalCandidate,
    Risk,
    TestCase,
)


class DataRepository(Protocol):
    """Read-only access to Spectrace domain records."""

    def list_requirements(self) -> list[Requirement]: ...

    def get_requirement(self, requirement_id: str) -> Requirement | None: ...

    def list_components(self) -> list[Component]: ...

    def list_risks(self) -> list[Risk]: ...

    def list_test_cases(self) -> list[TestCase]: ...

    def close(self) -> None: ...


@runtime_checkable
class GraphRepository(DataRepository, Protocol):
    """Capabilities provided only by an authoritative graph persistence backend."""

    def verify_connectivity(self) -> None: ...

    def transitive_dependencies(self, requirement_id: str, depth: int) -> list[Requirement]: ...

    def downstream_impact(self, requirement_id: str, depth: int) -> list[Requirement]: ...

    def components_for_requirement(self, requirement_id: str) -> list[Component]: ...

    def requirements_for_component(self, component_id: str) -> list[Requirement]: ...

    def shortest_path(self, source_id: str, target_id: str) -> GraphPath | None: ...

    def dependency_cycles(self) -> list[list[str]]: ...

    def unverified_risks(self) -> list[Risk]: ...

    def orphan_nodes(self) -> list[GraphNode]: ...


@runtime_checkable
class RetrievalRepository(GraphRepository, Protocol):
    """Native lexical, vector, and graph candidate retrieval capabilities."""

    def lexical_candidates(
        self, query: str, entity_types: list[str], limit: int
    ) -> list[RetrievalCandidate]: ...

    def semantic_candidates(
        self, embedding: list[float], entity_types: list[str], limit: int
    ) -> list[RetrievalCandidate]: ...

    def graph_candidates(
        self,
        seed_ids: list[str],
        entity_types: list[str],
        relationships: list[str],
        depth: int,
        limit: int,
    ) -> list[RetrievalCandidate]: ...
