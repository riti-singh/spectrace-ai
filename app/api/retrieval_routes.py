"""Typed hybrid traceability retrieval endpoint."""

from fastapi import APIRouter

from app.core.dependencies import RetrievalDependency
from app.models import RetrievalRequest, RetrievalResponse

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
def search(request: RetrievalRequest, service: RetrievalDependency) -> RetrievalResponse:
    return service.search(request)
