"""Version-one HTTP routes for deterministic traceability data."""

from typing import Annotated

from fastapi import APIRouter, Path, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

from app.core.dependencies import RepositoryDependency, TraceabilityDependency
from app.models import (
    Component,
    Requirement,
    RequirementTraceability,
    Risk,
    TestCase,
    TraceabilitySummary,
)
from app.services.traceability import RequirementNotFoundError

router = APIRouter()
RequirementPath = Annotated[str, Path(pattern=r"^REQ-\d{3}$", examples=["REQ-001"])]


class HealthResponse(BaseModel):
    status: str
    service: str


def _not_found(requirement_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "requirement_not_found",
            "message": f"Requirement '{requirement_id}' was not found.",
        },
    )


@router.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="spectrace-ai")


@router.get("/requirements", response_model=list[Requirement], tags=["requirements"])
def list_requirements(repository: RepositoryDependency) -> list[Requirement]:
    return repository.list_requirements()


@router.get(
    "/requirements/{requirement_id}",
    response_model=Requirement,
    tags=["requirements"],
)
def get_requirement(
    requirement_id: RequirementPath, repository: RepositoryDependency
) -> Requirement:
    requirement = repository.get_requirement(requirement_id)
    if requirement is None:
        raise _not_found(requirement_id)
    return requirement


@router.get("/components", response_model=list[Component], tags=["catalog"])
def list_components(repository: RepositoryDependency) -> list[Component]:
    return repository.list_components()


@router.get("/risks", response_model=list[Risk], tags=["catalog"])
def list_risks(repository: RepositoryDependency) -> list[Risk]:
    return repository.list_risks()


@router.get("/test-cases", response_model=list[TestCase], tags=["test planning"])
def list_test_cases(repository: RepositoryDependency) -> list[TestCase]:
    return repository.list_test_cases()


@router.get(
    "/traceability/summary",
    response_model=TraceabilitySummary,
    tags=["traceability"],
)
def traceability_summary(service: TraceabilityDependency) -> TraceabilitySummary:
    return service.get_summary()


@router.get(
    "/traceability/uncovered",
    response_model=list[Requirement],
    tags=["traceability"],
)
def uncovered_requirements(service: TraceabilityDependency) -> list[Requirement]:
    return service.get_uncovered_requirements()


@router.get(
    "/traceability/requirements/{requirement_id}",
    response_model=RequirementTraceability,
    tags=["traceability"],
)
def requirement_traceability(
    requirement_id: RequirementPath, service: TraceabilityDependency
) -> RequirementTraceability:
    try:
        return service.get_requirement_traceability(requirement_id)
    except RequirementNotFoundError as exc:
        raise _not_found(requirement_id) from exc
