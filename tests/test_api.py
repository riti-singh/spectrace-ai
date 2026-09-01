"""FastAPI contract tests."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import DATA_FILE


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "spectrace-ai"}


@pytest.mark.parametrize(
    ("path", "expected_count"),
    [
        ("/requirements", 16),
        ("/components", 7),
        ("/risks", 7),
        ("/test-cases", 9),
        ("/traceability/uncovered", 4),
    ],
)
def test_collection_endpoints(client: TestClient, path: str, expected_count: int) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert len(response.json()) == expected_count


def test_get_requirement(client: TestClient) -> None:
    response = client.get("/requirements/REQ-001")

    assert response.status_code == 200
    assert response.json()["title"] == "Initial satellite acquisition"


def test_traceability_summary(client: TestClient) -> None:
    response = client.get("/traceability/summary")

    assert response.status_code == 200
    assert response.json()["coverage_percentage"] == 75.0


def test_traceability_detail(client: TestClient) -> None:
    response = client.get("/traceability/requirements/REQ-003")
    payload = response.json()

    assert response.status_code == 200
    assert payload["requirement"]["id"] == "REQ-003"
    assert [item["id"] for item in payload["direct_dependencies"]] == [
        "REQ-001",
        "REQ-002",
    ]
    assert [item["id"] for item in payload["test_cases"]] == ["TST-003"]


@pytest.mark.parametrize(
    "path",
    ["/requirements/REQ-999", "/traceability/requirements/REQ-999"],
)
def test_missing_requirement_has_useful_error(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "requirement_not_found",
        "message": "Requirement 'REQ-999' was not found.",
    }


def test_malformed_requirement_id_is_rejected(client: TestClient) -> None:
    response = client.get("/requirements/not-an-id")

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_pattern_mismatch"


def test_dataset_failure_returns_controlled_api_error(tmp_path: Path) -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    payload["requirements"][0]["component_ids"].append("CMP-999")
    broken_file = tmp_path / "broken.json"
    broken_file.write_text(json.dumps(payload), encoding="utf-8")
    application = create_app(Settings(data_file=broken_file))

    with TestClient(application) as broken_client:
        response = broken_client.get("/requirements")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "dataset_unavailable"
    assert "CMP-999" in response.json()["detail"]["message"]


def test_api_output_is_deterministic(client: TestClient) -> None:
    responses = [client.get("/traceability/summary").content for _ in range(5)]

    assert len(set(responses)) == 1
