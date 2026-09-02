"""Neo4j-only graph health and bounded traversal endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.core.dependencies import GraphDependency
from app.models import (
    Component,
    DependencyCycle,
    DependencyTraversal,
    GraphHealth,
    GraphNode,
    GraphPath,
    Risk,
)
from app.repositories import MAX_PATH_DEPTH
from app.services.graph import TraceabilityPathNotFoundError
from app.services.traceability import RequirementNotFoundError

router = APIRouter(prefix="/graph", tags=["graph"])
RequirementPath = Annotated[str, Path(pattern=r"^REQ-\d{3}$", examples=["REQ-003"])]
EntityIdQuery = Annotated[
    str,
    Query(pattern=r"^(REQ|CMP|RSK|TST)-\d{3}$", examples=["REQ-003"]),
]
TraversalDepth = Annotated[int, Query(ge=1, le=MAX_PATH_DEPTH)]


def _requirement_not_found(requirement_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "requirement_not_found",
            "message": f"Requirement '{requirement_id}' was not found.",
        },
    )


@router.get("/health", response_model=GraphHealth)
def graph_health(service: GraphDependency) -> GraphHealth:
    return service.health()


@router.get(
    "/requirements/{requirement_id}/dependencies",
    response_model=DependencyTraversal,
)
def dependencies(
    requirement_id: RequirementPath,
    service: GraphDependency,
    depth: TraversalDepth = 5,
) -> DependencyTraversal:
    try:
        return service.dependencies(requirement_id, depth)
    except RequirementNotFoundError as exc:
        raise _requirement_not_found(requirement_id) from exc


@router.get(
    "/requirements/{requirement_id}/impact",
    response_model=DependencyTraversal,
)
def impact(
    requirement_id: RequirementPath,
    service: GraphDependency,
    depth: TraversalDepth = 5,
) -> DependencyTraversal:
    try:
        return service.impact(requirement_id, depth)
    except RequirementNotFoundError as exc:
        raise _requirement_not_found(requirement_id) from exc


@router.get(
    "/requirements/{requirement_id}/components",
    response_model=list[Component],
)
def components(requirement_id: RequirementPath, service: GraphDependency) -> list[Component]:
    try:
        return service.components(requirement_id)
    except RequirementNotFoundError as exc:
        raise _requirement_not_found(requirement_id) from exc


@router.get("/path", response_model=GraphPath)
def shortest_path(
    service: GraphDependency,
    source_id: EntityIdQuery,
    target_id: EntityIdQuery,
) -> GraphPath:
    try:
        return service.shortest_path(source_id, target_id)
    except TraceabilityPathNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "traceability_path_not_found",
                "message": f"No bounded graph path connects '{source_id}' and '{target_id}'.",
            },
        ) from exc


@router.get("/cycles", response_model=list[DependencyCycle])
def cycles(service: GraphDependency) -> list[DependencyCycle]:
    return service.cycles()


@router.get("/risks/unverified", response_model=list[Risk])
def unverified_risks(service: GraphDependency) -> list[Risk]:
    return service.unverified_risks()


@router.get("/orphans", response_model=list[GraphNode])
def orphans(service: GraphDependency) -> list[GraphNode]:
    return service.orphans()
