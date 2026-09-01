"""FastAPI dependency providers."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.repositories import DataRepository, JsonDataRepository
from app.repositories.json_repository import DatasetLoadError
from app.services.traceability import TraceabilityService


@lru_cache
def _repository_for_path(data_file: str) -> JsonDataRepository:
    from pathlib import Path

    return JsonDataRepository(Path(data_file))


def get_repository(settings: Annotated[Settings, Depends(get_settings)]) -> DataRepository:
    """Provide the configured repository and hide internal dataset details from clients."""

    try:
        return _repository_for_path(str(settings.data_file.resolve()))
    except DatasetLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "dataset_unavailable", "message": str(exc)},
        ) from exc


def get_traceability_service(
    repository: Annotated[DataRepository, Depends(get_repository)],
) -> TraceabilityService:
    return TraceabilityService(repository)


RepositoryDependency = Annotated[DataRepository, Depends(get_repository)]
TraceabilityDependency = Annotated[TraceabilityService, Depends(get_traceability_service)]
