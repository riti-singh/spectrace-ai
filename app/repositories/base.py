"""Repository contracts used by services and API dependencies."""

from typing import Protocol

from app.models import Component, Requirement, Risk, TestCase


class DataRepository(Protocol):
    """Read-only access to Spectrace domain records."""

    def list_requirements(self) -> list[Requirement]: ...

    def get_requirement(self, requirement_id: str) -> Requirement | None: ...

    def list_components(self) -> list[Component]: ...

    def list_risks(self) -> list[Risk]: ...

    def list_test_cases(self) -> list[TestCase]: ...
