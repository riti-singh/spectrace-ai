from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_retrieval_service
from app.main import create_app
from app.models import RetrievalResponse


class StubService:
    def search(self, request):
        return RetrievalResponse(
            query=request.query,
            mode=request.mode,
            result_count=0,
            results=[],
        )


def test_json_backend_rejects_retrieval_without_changing_existing_contract(client) -> None:
    response = client.post("/retrieval/search", json={"query": "thermal protection"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "neo4j_backend_required"


def test_retrieval_endpoint_has_typed_response_and_validation() -> None:
    application = create_app(Settings(_env_file=None))
    application.dependency_overrides[get_retrieval_service] = lambda: StubService()
    with TestClient(application) as client:
        response = client.post(
            "/retrieval/search",
            json={"query": "firmware recovery", "mode": "semantic", "result_count": 5},
        )
        invalid = client.post("/retrieval/search", json={"query": "x", "result_count": 100})

    assert response.status_code == 200
    assert response.json() == {
        "query": "firmware recovery",
        "mode": "semantic",
        "result_count": 0,
        "results": [],
    }
    assert invalid.status_code == 422


def test_retrieval_evaluation_is_available_without_neo4j(client) -> None:
    response = client.get("/retrieval/evaluation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["benchmark"] == "asteria-hybrid-retrieval-v1"
    assert payload["query_count"] == 8
    assert [item["mode"] for item in payload["metrics"]] == [
        "lexical",
        "semantic",
        "graph",
        "hybrid",
    ]
    assert payload["metrics"][-1]["precision_at_k"] == 0.65
