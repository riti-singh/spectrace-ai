import math

import pytest
from pydantic import ValidationError

from app.models import RetrievalMode
from app.retrieval.comparison import (
    StrategyEvaluation,
    evaluate_strategies,
    evaluate_strategy,
    inspection_depth,
)
from app.retrieval.evaluation import EvaluationDataset
from tests.conftest import ALPHA_QUERY, STUB_RANKINGS
from tests.fakes import StubSearcher


def strategy(results: list[StrategyEvaluation], mode: RetrievalMode) -> StrategyEvaluation:
    return next(item for item in results if item.mode is mode)


def test_every_strategy_is_scored_with_the_shared_metric_implementation(
    strategy_results: list[StrategyEvaluation],
) -> None:
    lexical = strategy(strategy_results, RetrievalMode.LEXICAL)

    alpha_ndcg = 7 / (7 + 3 / math.log2(3))
    beta_ndcg = 7 / (7 + 1 / math.log2(3))
    assert lexical.metrics.model_dump() == pytest.approx(
        {
            "precision_at_k": 0.5,
            "recall_at_k": 2 / 3,
            "mrr": 1.0,
            "ndcg_at_k": (alpha_ndcg + beta_ndcg + 1.0) / 3,
        }
    )
    assert [item.mode for item in strategy_results] == list(RetrievalMode)


def test_per_query_rows_capture_ranking_and_expected_artifacts(
    strategy_results: list[StrategyEvaluation],
) -> None:
    alpha = strategy(strategy_results, RetrievalMode.LEXICAL).queries[0]

    assert alpha.case == "alpha"
    assert alpha.query == ALPHA_QUERY
    assert alpha.relevant_ids == ["REQ-005", "TST-004"]
    assert alpha.retrieved_ids == STUB_RANKINGS[RetrievalMode.LEXICAL, ALPHA_QUERY]
    assert [artifact.rank for artifact in alpha.retrieved] == [1, 2, 3, 4]
    assert [artifact.grade for artifact in alpha.retrieved] == [3, 0, 2, 0]
    assert alpha.first_relevant_rank == 1
    assert alpha.below_cutoff_ids == ["TST-004"]
    assert alpha.missing_ids == []


def test_evaluation_is_deterministic_across_repeated_runs(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    first = evaluate_strategies(
        stub_searcher, comparison_dataset, list(RetrievalMode), measure_latency=False
    )
    second = evaluate_strategies(
        stub_searcher, comparison_dataset, list(RetrievalMode), measure_latency=False
    )

    assert [item.model_dump_json() for item in first] == [item.model_dump_json() for item in second]
    assert all(query.latency_ms is None for item in first for query in item.queries)
    assert all(item.mean_latency_ms is None for item in first)


def test_latency_is_measured_when_requested(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    evaluated = evaluate_strategy(stub_searcher, comparison_dataset, RetrievalMode.HYBRID)

    assert evaluated.mean_latency_ms is not None
    assert all(query.latency_ms is not None for query in evaluated.queries)


def test_strategies_that_return_nothing_score_zero(
    strategy_results: list[StrategyEvaluation],
) -> None:
    alpha = strategy(strategy_results, RetrievalMode.GRAPH).queries[0]

    assert alpha.retrieved == []
    assert alpha.first_relevant_rank is None
    assert alpha.missing_ids == ["REQ-005", "TST-004"]
    assert alpha.metrics.model_dump() == {
        "precision_at_k": 0.0,
        "recall_at_k": 0.0,
        "mrr": 0.0,
        "ndcg_at_k": 0.0,
    }


def test_requests_reuse_the_case_definition_and_inspect_beyond_the_cutoff(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    evaluate_strategy(stub_searcher, comparison_dataset, RetrievalMode.GRAPH, depth=6)

    assert [request.mode for request in stub_searcher.requests] == [RetrievalMode.GRAPH] * 3
    assert [request.result_count for request in stub_searcher.requests] == [6, 6, 6]
    assert stub_searcher.requests[0].query == ALPHA_QUERY


def test_default_inspection_depth_doubles_the_cutoff_within_the_request_bound() -> None:
    dataset = EvaluationDataset.model_validate(
        {
            "name": "depth",
            "k": 20,
            "cases": [
                {
                    "name": "case",
                    "request": {"query": "depth bound"},
                    "relevance": {"REQ-001": 1},
                }
            ],
        }
    )

    assert inspection_depth(dataset) == 25
    assert inspection_depth(dataset, 20) == 20


def test_depth_below_the_cutoff_is_rejected(comparison_dataset: EvaluationDataset) -> None:
    with pytest.raises(ValueError, match="inspection depth"):
        inspection_depth(comparison_dataset, 1)


def test_at_least_one_strategy_is_required(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    with pytest.raises(ValueError, match="at least one retrieval strategy"):
        evaluate_strategies(stub_searcher, comparison_dataset, [])


def test_repeated_strategies_are_evaluated_once(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    evaluated = evaluate_strategies(
        stub_searcher,
        comparison_dataset,
        [RetrievalMode.HYBRID, RetrievalMode.HYBRID],
        measure_latency=False,
    )

    assert [item.mode for item in evaluated] == [RetrievalMode.HYBRID]


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "no cases", "k": 2, "cases": []},
        {"name": "bad cutoff", "k": 0, "cases": [{"name": "case", "request": {"query": "ab"}}]},
        {
            "name": "unknown field",
            "k": 2,
            "cases": [
                {
                    "name": "case",
                    "request": {"query": "valid query"},
                    "relevance": {"REQ-001": 1},
                    "notes": "unsupported",
                }
            ],
        },
    ],
)
def test_malformed_datasets_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EvaluationDataset.model_validate(payload)
