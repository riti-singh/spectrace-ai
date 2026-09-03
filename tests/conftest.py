"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app
from app.models import RetrievalMode
from app.repositories import JsonDataRepository
from app.retrieval.comparison import StrategyEvaluation, evaluate_strategies
from app.retrieval.evaluation import EvaluationDataset
from tests.fakes import StubSearcher

DATA_FILE = PROJECT_ROOT / "data" / "asteria_dataset.json"

ALPHA_QUERY = "thermal shutdown verification"
BETA_QUERY = "firmware rollback recovery"
GAMMA_QUERY = "emergency traffic priority"

STUB_RANKINGS: dict[tuple[RetrievalMode, str], list[str]] = {
    (RetrievalMode.LEXICAL, ALPHA_QUERY): ["REQ-005", "CMP-001", "TST-004", "REQ-001"],
    (RetrievalMode.SEMANTIC, ALPHA_QUERY): ["TST-004", "REQ-005"],
    (RetrievalMode.GRAPH, ALPHA_QUERY): [],
    (RetrievalMode.HYBRID, ALPHA_QUERY): ["REQ-005", "TST-004"],
    (RetrievalMode.LEXICAL, BETA_QUERY): ["REQ-009", "REQ-002"],
    (RetrievalMode.SEMANTIC, BETA_QUERY): ["REQ-002", "REQ-009"],
    (RetrievalMode.GRAPH, BETA_QUERY): ["RSK-006", "CMP-004"],
    (RetrievalMode.HYBRID, BETA_QUERY): ["RSK-006", "REQ-009"],
    (RetrievalMode.LEXICAL, GAMMA_QUERY): ["REQ-011", "REQ-012"],
    (RetrievalMode.SEMANTIC, GAMMA_QUERY): ["REQ-011", "REQ-013"],
    (RetrievalMode.GRAPH, GAMMA_QUERY): ["CMP-007", "RSK-007"],
    (RetrievalMode.HYBRID, GAMMA_QUERY): ["CMP-007", "REQ-011"],
}


@pytest.fixture
def repository() -> JsonDataRepository:
    return JsonDataRepository(DATA_FILE)


@pytest.fixture
def client() -> Iterator[TestClient]:
    application = create_app(Settings(data_file=DATA_FILE))
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def comparison_dataset() -> EvaluationDataset:
    return EvaluationDataset.model_validate(
        {
            "name": "stub-comparison",
            "k": 2,
            "cases": [
                {
                    "name": "alpha",
                    "request": {"query": ALPHA_QUERY},
                    "relevance": {"REQ-005": 3, "TST-004": 2},
                },
                {
                    "name": "beta",
                    "request": {"query": BETA_QUERY},
                    "relevance": {"REQ-009": 3, "RSK-006": 1},
                },
                {
                    "name": "gamma",
                    "request": {"query": GAMMA_QUERY},
                    "relevance": {"REQ-011": 3},
                },
            ],
        }
    )


@pytest.fixture
def stub_searcher() -> StubSearcher:
    return StubSearcher(STUB_RANKINGS)


@pytest.fixture
def strategy_results(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> list[StrategyEvaluation]:
    return evaluate_strategies(
        stub_searcher, comparison_dataset, list(RetrievalMode), measure_latency=False
    )
