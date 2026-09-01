"""Deterministic traceability calculations over repository data."""

from collections import Counter

from app.models import (
    Priority,
    Requirement,
    RequirementTraceability,
    RequirementType,
    TraceabilitySummary,
)
from app.repositories import DataRepository


class RequirementNotFoundError(LookupError):
    """Raised when traceability is requested for an unknown requirement."""


class TraceabilityService:
    """Compute coverage and relationships without probabilistic behavior."""

    def __init__(self, repository: DataRepository) -> None:
        self._repository = repository

    def get_summary(self) -> TraceabilitySummary:
        requirements = self._repository.list_requirements()
        covered_ids = self._covered_requirement_ids()
        total = len(requirements)
        covered = sum(requirement.id in covered_ids for requirement in requirements)
        priority_counts = Counter(requirement.priority for requirement in requirements)
        type_counts = Counter(requirement.requirement_type for requirement in requirements)

        return TraceabilitySummary(
            total_requirements=total,
            covered_requirements=covered,
            uncovered_requirements=total - covered,
            coverage_percentage=round((covered / total * 100) if total else 0.0, 2),
            requirements_by_priority={priority: priority_counts[priority] for priority in Priority},
            requirements_by_type={
                requirement_type: type_counts[requirement_type]
                for requirement_type in RequirementType
            },
        )

    def get_uncovered_requirements(self) -> list[Requirement]:
        covered_ids = self._covered_requirement_ids()
        return [
            requirement
            for requirement in self._repository.list_requirements()
            if requirement.id not in covered_ids
        ]

    def get_requirement_traceability(self, requirement_id: str) -> RequirementTraceability:
        requirement = self._repository.get_requirement(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(requirement_id)

        tests = [
            test_case
            for test_case in self._repository.list_test_cases()
            if requirement_id in test_case.requirement_ids
        ]
        requirements_by_id = {item.id: item for item in self._repository.list_requirements()}
        components_by_id = {item.id: item for item in self._repository.list_components()}
        risks_by_id = {item.id: item for item in self._repository.list_risks()}
        return RequirementTraceability(
            requirement=requirement,
            test_cases=tests,
            direct_dependencies=[
                requirements_by_id[item_id] for item_id in requirement.dependency_ids
            ],
            components=[components_by_id[item_id] for item_id in requirement.component_ids],
            risks=[risks_by_id[item_id] for item_id in requirement.risk_ids],
        )

    def _covered_requirement_ids(self) -> set[str]:
        return {
            requirement_id
            for test_case in self._repository.list_test_cases()
            for requirement_id in test_case.requirement_ids
        }
