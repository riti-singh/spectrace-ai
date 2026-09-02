import math

import pytest
from pydantic import ValidationError

from app.retrieval.evaluation import EvaluationCase, mean_metrics, metrics_at_k


def test_metrics_at_k_uses_binary_hits_and_graded_gain() -> None:
    metrics = metrics_at_k(["B", "A", "X"], {"A": 3, "B": 1, "C": 2}, 3)

    expected_dcg = 1.0 + 7.0 / math.log2(3)
    ideal_dcg = 7.0 + 3.0 / math.log2(3) + 1.0 / math.log2(4)
    assert metrics == pytest.approx(
        {
            "precision_at_k": 2 / 3,
            "recall_at_k": 2 / 3,
            "mrr": 1.0,
            "ndcg_at_k": expected_dcg / ideal_dcg,
        }
    )


def test_metrics_handle_no_retrieved_relevant_result() -> None:
    assert metrics_at_k([], {"A": 1}, 5) == {
        "precision_at_k": 0.0,
        "recall_at_k": 0.0,
        "mrr": 0.0,
        "ndcg_at_k": 0.0,
    }


def test_mean_metrics_requires_rows() -> None:
    with pytest.raises(ValueError, match="at least one"):
        mean_metrics([])


@pytest.mark.parametrize("relevance", [{"bad": 1}, {"REQ-001": 0}, {"REQ-001": 4}])
def test_evaluation_case_rejects_invalid_judgments(relevance: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate(
            {"name": "invalid", "request": {"query": "valid query"}, "relevance": relevance}
        )
