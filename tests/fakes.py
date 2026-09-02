"""Small deterministic test doubles shared by Neo4j-focused unit tests."""

from collections.abc import Callable, Mapping
from typing import Any


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
