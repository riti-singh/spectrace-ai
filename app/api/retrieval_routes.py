"""Typed hybrid traceability retrieval and evaluation endpoints."""

from fastapi import APIRouter

from app.core.config import PROJECT_ROOT
from app.core.dependencies import RetrievalDependency
from app.models import RetrievalEvaluationSummary, RetrievalRequest, RetrievalResponse

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
def search(request: RetrievalRequest, service: RetrievalDependency) -> RetrievalResponse:
    return service.search(request)


@router.get("/evaluation", response_model=RetrievalEvaluationSummary)
def evaluation_summary() -> RetrievalEvaluationSummary:
    """Return the checked-in, reproducible synthetic benchmark snapshot."""

    path = PROJECT_ROOT / "data" / "retrieval_evaluation_results.json"
    return RetrievalEvaluationSummary.model_validate_json(path.read_text(encoding="utf-8"))
