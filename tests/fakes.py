"""Small deterministic test doubles shared by unit tests."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.models import (
    GraphEntityType,
    RetrievalExplanation,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)

_ENTITY_TYPES = {
    "REQ": GraphEntityType.REQUIREMENT,
    "CMP": GraphEntityType.COMPONENT,
    "RSK": GraphEntityType.RISK,
    "TST": GraphEntityType.TEST_CASE,
}


class FakeDriver:
    def __init__(
        self,
        handler: Callable[[str, Mapping[str, Any]], list[dict[str, Any]]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.handler = handler or (lambda _query, _parameters: [])
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def execute_query(self, query: str, **kwargs: Any) -> tuple[list[dict[str, Any]], None, None]:
        parameters = kwargs.get("parameters_", {})
        self.calls.append({"query": query, **kwargs})
        if self.error is not None:
            raise self.error
        return self.handler(query, parameters), None, None

    def close(self) -> None:
        self.closed = True


class StubSearcher:
    """Replay canned rankings per (mode, query) without any repository or index."""

    def __init__(self, rankings: Mapping[tuple[RetrievalMode, str], Sequence[str]]) -> None:
        self._rankings = rankings
        self.requests: list[RetrievalRequest] = []

    def __call__(self, request: RetrievalRequest) -> RetrievalResponse:
        self.requests.append(request)
        ranked = list(self._rankings.get((request.mode, request.query), ()))
        results = [
            RetrievalResult(
                id=entity_id,
                entity_type=_ENTITY_TYPES[entity_id[:3]],
                title=f"Title {entity_id}",
                text=f"Text for {entity_id}",
                score=round(1.0 - index / 100, 4),
                explanation=RetrievalExplanation(fusion_method="stub"),
            )
            for index, entity_id in enumerate(ranked[: request.result_count])
        ]
        return RetrievalResponse(
            query=request.query,
            mode=request.mode,
            result_count=len(results),
            results=results,
        )
