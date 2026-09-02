import pytest
from pydantic import ValidationError

from app.models import RetrievalRequest


def test_retrieval_request_defaults_are_bounded() -> None:
    request = RetrievalRequest(query="thermal protection")

    assert len(request.entity_types) == 4
    assert len(request.relationships) == 4
    assert request.result_count == 10
    assert request.graph_depth == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "x"},
        {"query": "valid", "result_count": 26},
        {"query": "valid", "graph_depth": 4},
        {"query": "valid", "entity_types": ["Risk", "Risk"]},
        {"query": "valid", "relationships": ["VERIFIES", "VERIFIES"]},
        {"query": "valid", "entity_types": []},
    ],
)
def test_retrieval_request_rejects_unbounded_or_duplicate_filters(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        RetrievalRequest.model_validate(payload)
