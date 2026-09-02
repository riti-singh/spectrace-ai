"""Validated JSON-backed implementation of the domain repository."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.models import Component, Dataset, Requirement, Risk, TestCase
from app.repositories.exceptions import DatasetLoadError


def load_dataset(data_file: Path) -> Dataset:
    """Load a JSON dataset and enforce complete Pydantic and reference validation."""

    try:
        raw_data = json.loads(data_file.read_text(encoding="utf-8"))
        return Dataset.model_validate(raw_data)
    except FileNotFoundError as exc:
        raise DatasetLoadError(f"dataset file not found: {data_file}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetLoadError(
            f"dataset contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except ValidationError as exc:
        raise DatasetLoadError(f"dataset integrity validation failed: {exc}") from exc


class JsonDataRepository:
    """Load and serve an immutable snapshot of a JSON domain dataset."""

    def __init__(self, data_file: Path) -> None:
        self._data_file = data_file
        self._dataset = load_dataset(data_file)
        self._requirements_by_id = {item.id: item for item in self._dataset.requirements}

    def list_requirements(self) -> list[Requirement]:
        return sorted(self._dataset.requirements, key=lambda item: item.id)

    def get_requirement(self, requirement_id: str) -> Requirement | None:
        return self._requirements_by_id.get(requirement_id)

    def list_components(self) -> list[Component]:
        return sorted(self._dataset.components, key=lambda item: item.id)

    def list_risks(self) -> list[Risk]:
        return sorted(self._dataset.risks, key=lambda item: item.id)

    def list_test_cases(self) -> list[TestCase]:
        return sorted(self._dataset.test_cases, key=lambda item: item.id)

    def close(self) -> None:
        """Satisfy the repository lifecycle contract; JSON holds no external resources."""
