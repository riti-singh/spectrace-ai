"""FastAPI dependency providers and lazy repository lifecycle management."""

from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings
from app.repositories import (
    DataRepository,
    DatasetLoadError,
    GraphRepository,
    JsonDataRepository,
    Neo4jRepository,
    RepositoryConnectionError,
)
from app.services.graph import GraphTraversalService
from app.services.traceability import TraceabilityService


class RepositoryManager:
    """Lazily construct one repository per app and close external resources on shutdown."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository: DataRepository | None = None
        self._lock = Lock()

    def get(self) -> DataRepository:
        if self._repository is None:
            with self._lock:
                if self._repository is None:
                    self._repository = self._create()
        return self._repository

    def close(self) -> None:
        with self._lock:
            if self._repository is not None:
                self._repository.close()
                self._repository = None

    def _create(self) -> DataRepository:
        if self._settings.repository_backend == "json":
            return JsonDataRepository(self._settings.data_file.resolve())
        password = self._settings.neo4j_password
        if password is None:  # Defensive; Settings rejects this configuration first.
            raise RepositoryConnectionError("Neo4j password is not configured")
        return Neo4jRepository(
            uri=self._settings.neo4j_uri,
            username=self._settings.neo4j_username,
            password=password.get_secret_value(),
            database=self._settings.neo4j_database,
        )


def get_repository(request: Request) -> DataRepository:
    """Resolve the selected backend and translate initialization failures for API clients."""

    manager: RepositoryManager = request.app.state.repository_manager
    try:
        return manager.get()
    except DatasetLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "dataset_unavailable", "message": str(exc)},
        ) from exc
    except RepositoryConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "repository_unavailable",
                "message": "The configured persistence backend is unavailable.",
            },
        ) from exc


def get_traceability_service(
    repository: Annotated[DataRepository, Depends(get_repository)],
) -> TraceabilityService:
    return TraceabilityService(repository)


def get_graph_service(
    repository: Annotated[DataRepository, Depends(get_repository)],
) -> GraphTraversalService:
    if not isinstance(repository, GraphRepository):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "neo4j_backend_required",
                "message": "Graph traversal requires SPECTRACE_REPOSITORY_BACKEND=neo4j.",
            },
        )
    return GraphTraversalService(repository)


RepositoryDependency = Annotated[DataRepository, Depends(get_repository)]
TraceabilityDependency = Annotated[TraceabilityService, Depends(get_traceability_service)]
GraphDependency = Annotated[GraphTraversalService, Depends(get_graph_service)]
