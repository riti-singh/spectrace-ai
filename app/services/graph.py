"""Deterministic bounded graph traversal orchestration."""

from app.models import (
    Component,
    DependencyCycle,
    DependencyTraversal,
    GraphHealth,
    GraphNode,
    GraphPath,
    Requirement,
    Risk,
)
from app.repositories import MAX_PATH_DEPTH, GraphRepository
from app.services.traceability import RequirementNotFoundError


class InvalidTraversalDepthError(ValueError):
    """Raised when callers bypass API validation with an unsafe traversal depth."""


class TraceabilityPathNotFoundError(LookupError):
    """Raised when no bounded path connects the requested domain entities."""


class GraphTraversalService:
    """Expose explainable graph operations while enforcing a global traversal bound."""

    def __init__(self, repository: GraphRepository) -> None:
        self._repository = repository

    def health(self) -> GraphHealth:
        self._repository.verify_connectivity()
        database = getattr(self._repository, "database", "neo4j")
        return GraphHealth(status="ok", backend="neo4j", database=database)

    def dependencies(self, requirement_id: str, depth: int) -> DependencyTraversal:
        self._require_requirement(requirement_id)
        self._validate_depth(depth)
        return DependencyTraversal(
            requirement_id=requirement_id,
            depth=depth,
            requirements=self._repository.transitive_dependencies(requirement_id, depth),
        )

    def impact(self, requirement_id: str, depth: int) -> DependencyTraversal:
        self._require_requirement(requirement_id)
        self._validate_depth(depth)
        return DependencyTraversal(
            requirement_id=requirement_id,
            depth=depth,
            requirements=self._repository.downstream_impact(requirement_id, depth),
        )

    def components(self, requirement_id: str) -> list[Component]:
        self._require_requirement(requirement_id)
        return self._repository.components_for_requirement(requirement_id)

    def requirements_for_component(self, component_id: str) -> list[Requirement]:
        return self._repository.requirements_for_component(component_id)

    def shortest_path(self, source_id: str, target_id: str) -> GraphPath:
        path = self._repository.shortest_path(source_id, target_id)
        if path is None:
            raise TraceabilityPathNotFoundError(f"{source_id}:{target_id}")
        return path

    def cycles(self) -> list[DependencyCycle]:
        canonical_cycles: set[tuple[str, ...]] = set()
        for raw_cycle in self._repository.dependency_cycles():
            core = raw_cycle[:-1] if raw_cycle and raw_cycle[0] == raw_cycle[-1] else raw_cycle
            if not core:
                continue
            rotations = [tuple(core[index:] + core[:index]) for index in range(len(core))]
            canonical = min(rotations)
            canonical_cycles.add((*canonical, canonical[0]))
        return [DependencyCycle(requirement_ids=list(cycle)) for cycle in sorted(canonical_cycles)]

    def unverified_risks(self) -> list[Risk]:
        return self._repository.unverified_risks()

    def orphans(self) -> list[GraphNode]:
        return self._repository.orphan_nodes()

    def _require_requirement(self, requirement_id: str) -> Requirement:
        requirement = self._repository.get_requirement(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(requirement_id)
        return requirement

    @staticmethod
    def _validate_depth(depth: int) -> None:
        if not 1 <= depth <= MAX_PATH_DEPTH:
            raise InvalidTraversalDepthError(
                f"depth must be between 1 and {MAX_PATH_DEPTH}, inclusive"
            )
