"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app
from app.repositories import JsonDataRepository

DATA_FILE = PROJECT_ROOT / "data" / "asteria_dataset.json"


@pytest.fixture
def repository() -> JsonDataRepository:
    return JsonDataRepository(DATA_FILE)


@pytest.fixture
def client() -> Iterator[TestClient]:
    application = create_app(Settings(data_file=DATA_FILE))
    with TestClient(application) as test_client:
        yield test_client
