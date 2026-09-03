import pytest

from app.models import RetrievalMode
from app.retrieval.comparison import StrategyEvaluation
from app.retrieval.failure_analysis import (
    FailureAnalysis,
    FailureCategory,
    FailureFinding,
    analyze_failures,
)


def findings_for(
    analysis: FailureAnalysis, category: FailureCategory, mode: RetrievalMode | None = None
) -> list[FailureFinding]:
    return [
        finding
        for finding in analysis.findings
        if finding.category is category and (mode is None or finding.mode is mode)
    ]


def test_single_strategy_failures_are_classified_from_measured_rankings(
    strategy_results: list[StrategyEvaluation],
) -> None:
    analysis = analyze_failures(strategy_results)

    empty = findings_for(analysis, FailureCategory.NO_RESULTS, RetrievalMode.GRAPH)
    assert [finding.case for finding in empty] == ["alpha"]
    below_cutoff = findings_for(analysis, FailureCategory.RANKED_BELOW_CUTOFF)
    assert [(finding.mode, finding.case, finding.entity_ids) for finding in below_cutoff] == [
        (RetrievalMode.LEXICAL, "alpha", ["TST-004"])
    ]
    missed = findings_for(analysis, FailureCategory.MISSING_RELEVANT, RetrievalMode.GRAPH)
    assert [(finding.case, finding.entity_ids) for finding in missed] == [
        ("alpha", ["REQ-005", "TST-004"]),
        ("beta", ["REQ-009"]),
        ("gamma", ["REQ-011"]),
    ]
    semantic_beta = findings_for(
        analysis, FailureCategory.TOP_RESULT_NOT_RELEVANT, RetrievalMode.SEMANTIC
    )
    assert [(finding.case, finding.entity_ids) for finding in semantic_beta] == [
        ("beta", ["REQ-002"])
    ]


def test_hybrid_improvements_and_regressions_are_ranked_by_metric_delta(
    strategy_results: list[StrategyEvaluation],
) -> None:
    analysis = analyze_failures(strategy_results)

    assert [
        finding.case for finding in findings_for(analysis, FailureCategory.HYBRID_IMPROVED)
    ] == ["alpha"]
    assert [
        finding.case for finding in findings_for(analysis, FailureCategory.HYBRID_REGRESSED)
    ] == ["beta", "gamma"]
    assert [delta.case for delta in analysis.top_improvements] == ["alpha"]
    assert [delta.case for delta in analysis.top_regressions] == ["gamma", "beta"]
    gamma = analysis.top_regressions[0]
    assert gamma.best_component_mode is RetrievalMode.LEXICAL
    assert gamma.best_component_score == pytest.approx(1.0)
    assert gamma.delta == pytest.approx(gamma.hybrid_score - gamma.best_component_score)
    assert analysis.top_regressions[1].delta > gamma.delta


def test_channel_contributions_are_attributed_to_unique_retrievals(
    strategy_results: list[StrategyEvaluation],
) -> None:
    analysis = analyze_failures(strategy_results)

    assert [
        (finding.case, finding.entity_ids)
        for finding in findings_for(analysis, FailureCategory.GRAPH_HELPED)
    ] == [("beta", ["RSK-006"])]
    assert [
        (finding.case, finding.entity_ids)
        for finding in findings_for(analysis, FailureCategory.VECTOR_HELPED)
    ] == [("alpha", ["TST-004"])]
    graph_hurt = findings_for(analysis, FailureCategory.GRAPH_HURT)
    assert [(finding.case, finding.entity_ids) for finding in graph_hurt] == [
        ("gamma", ["CMP-007"])
    ]
    assert graph_hurt[0].metric_delta is not None


def test_analysis_is_deterministic_and_counts_every_finding(
    strategy_results: list[StrategyEvaluation],
) -> None:
    first = analyze_failures(strategy_results)
    second = analyze_failures(strategy_results)

    assert first.model_dump_json() == second.model_dump_json()
    assert sum(first.category_counts.values()) == len(first.findings)
    assert list(first.category_counts) == sorted(first.category_counts)


def test_primary_metric_selects_the_comparison_dimension(
    strategy_results: list[StrategyEvaluation],
) -> None:
    analysis = analyze_failures(strategy_results, primary_metric="precision_at_k")

    assert analysis.primary_metric == "precision_at_k"
    assert [
        finding.case for finding in findings_for(analysis, FailureCategory.HYBRID_IMPROVED)
    ] == ["beta"]
    assert findings_for(analysis, FailureCategory.HYBRID_REGRESSED) == []


def test_large_tolerance_suppresses_comparison_findings(
    strategy_results: list[StrategyEvaluation],
) -> None:
    analysis = analyze_failures(strategy_results, tolerance=1.0)

    assert analysis.top_improvements == []
    assert analysis.top_regressions == []
    assert findings_for(analysis, FailureCategory.HYBRID_REGRESSED) == []


def test_runs_without_hybrid_report_only_per_query_failures(
    strategy_results: list[StrategyEvaluation],
) -> None:
    analysis = analyze_failures(
        [strategy for strategy in strategy_results if strategy.mode is not RetrievalMode.HYBRID]
    )

    assert analysis.top_improvements == []
    assert analysis.top_regressions == []
    assert all(
        finding.category
        in {
            FailureCategory.NO_RESULTS,
            FailureCategory.MISSING_RELEVANT,
            FailureCategory.RANKED_BELOW_CUTOFF,
            FailureCategory.TOP_RESULT_NOT_RELEVANT,
        }
        for finding in analysis.findings
    )


def test_hybrid_without_component_strategies_produces_no_comparison(
    strategy_results: list[StrategyEvaluation],
) -> None:
    analysis = analyze_failures(
        [strategy for strategy in strategy_results if strategy.mode is RetrievalMode.HYBRID]
    )

    assert analysis.top_improvements == []
    assert analysis.top_regressions == []


def test_attribution_skips_strategies_absent_from_the_run(
    strategy_results: list[StrategyEvaluation],
) -> None:
    without_semantic = [
        strategy for strategy in strategy_results if strategy.mode is not RetrievalMode.SEMANTIC
    ]

    analysis = analyze_failures(without_semantic)

    assert findings_for(analysis, FailureCategory.VECTOR_HELPED) == []
    assert findings_for(analysis, FailureCategory.GRAPH_HELPED)


def test_invalid_strategy_collections_are_rejected(
    strategy_results: list[StrategyEvaluation],
) -> None:
    with pytest.raises(ValueError, match="at least one evaluated strategy"):
        analyze_failures([])
    with pytest.raises(ValueError, match="only be evaluated once"):
        analyze_failures([strategy_results[0], strategy_results[0]])
    mismatched = strategy_results[1].model_copy(update={"queries": strategy_results[1].queries[:1]})
    with pytest.raises(ValueError, match="same dataset cases"):
        analyze_failures([strategy_results[0], mismatched])
