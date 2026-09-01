"""Deterministic traceability service tests."""

import pytest

from app.repositories import JsonDataRepository
from app.services.traceability import RequirementNotFoundError, TraceabilityService


@pytest.fixture
def service(repository: JsonDataRepository) -> TraceabilityService:
    return TraceabilityService(repository)


def test_summary_calculates_expected_coverage(service: TraceabilityService) -> None:
    summary = service.get_summary()

    assert summary.total_requirements == 16
    assert summary.covered_requirements == 12
    assert summary.uncovered_requirements == 4
    assert summary.coverage_percentage == 75.0
    assert sum(summary.requirements_by_priority.values()) == 16
    assert sum(summary.requirements_by_type.values()) == 16
    assert summary.requirements_by_priority["critical"] == 7
    assert summary.requirements_by_type["security"] == 3


def test_uncovered_requirements_are_exact_and_sorted(service: TraceabilityService) -> None:
    assert [item.id for item in service.get_uncovered_requirements()] == [
        "REQ-008",
        "REQ-012",
        "REQ-013",
        "REQ-016",
    ]


def test_requirement_traceability_resolves_direct_relationships(
    service: TraceabilityService,
) -> None:
    trace = service.get_requirement_traceability("REQ-003")

    assert [item.id for item in trace.test_cases] == ["TST-003"]
    assert [item.id for item in trace.direct_dependencies] == ["REQ-001", "REQ-002"]
    assert [item.id for item in trace.components] == ["CMP-001", "CMP-002", "CMP-003"]
    assert [item.id for item in trace.risks] == ["RSK-002"]


def test_requirement_traceability_reports_missing_id(service: TraceabilityService) -> None:
    with pytest.raises(RequirementNotFoundError):
        service.get_requirement_traceability("REQ-999")


def test_outputs_are_deterministic(service: TraceabilityService) -> None:
    summaries = [service.get_summary().model_dump_json() for _ in range(5)]
    traces = [service.get_requirement_traceability("REQ-004").model_dump_json() for _ in range(5)]

    assert len(set(summaries)) == 1
    assert len(set(traces)) == 1
