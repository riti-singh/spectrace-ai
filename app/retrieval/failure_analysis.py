"""Rule-based classification of retrieval failures from measured evaluation results."""

from collections import Counter
from collections.abc import Sequence
from enum import StrEnum

from pydantic import Field

from app.models import RetrievalMode
from app.models.domain import DomainModel
from app.retrieval.comparison import QueryEvaluation, StrategyEvaluation

DEFAULT_PRIMARY_METRIC = "ndcg_at_k"
DEFAULT_TOLERANCE = 1e-6
DEFAULT_HIGHLIGHT_LIMIT = 3

_COMPONENT_MODES = (RetrievalMode.LEXICAL, RetrievalMode.SEMANTIC, RetrievalMode.GRAPH)


class FailureCategory(StrEnum):
    """Categories derived only from retrieved rankings and graded judgments."""

    NO_RESULTS = "no_results"
    MISSING_RELEVANT = "missing_relevant"
    RANKED_BELOW_CUTOFF = "ranked_below_cutoff"
    TOP_RESULT_NOT_RELEVANT = "top_result_not_relevant"
    HYBRID_IMPROVED = "hybrid_improved"
    HYBRID_REGRESSED = "hybrid_regressed"
    GRAPH_HELPED = "graph_helped"
    GRAPH_HURT = "graph_hurt"
    VECTOR_HELPED = "vector_helped"


class FailureFinding(DomainModel):
    case: str
    query: str
    category: FailureCategory
    mode: RetrievalMode | None = None
    compared_mode: RetrievalMode | None = None
    entity_ids: list[str] = Field(default_factory=list)
    metric_delta: float | None = None
    detail: str


class StrategyDelta(DomainModel):
    case: str
    query: str
    metric: str
    hybrid_score: float
    best_component_mode: RetrievalMode
    best_component_score: float
    delta: float


class FailureAnalysis(DomainModel):
    primary_metric: str
    tolerance: float = Field(gt=0)
    category_counts: dict[str, int]
    findings: list[FailureFinding]
    top_improvements: list[StrategyDelta]
    top_regressions: list[StrategyDelta]


def analyze_failures(
    strategies: Sequence[StrategyEvaluation],
    *,
    primary_metric: str = DEFAULT_PRIMARY_METRIC,
    tolerance: float = DEFAULT_TOLERANCE,
    highlight_limit: int = DEFAULT_HIGHLIGHT_LIMIT,
) -> FailureAnalysis:
    """Classify per-query outcomes and cross-strategy deltas for the evaluated run."""

    if not strategies:
        raise ValueError("at least one evaluated strategy is required")
    by_mode = {strategy.mode: strategy for strategy in strategies}
    if len(by_mode) != len(strategies):
        raise ValueError("each retrieval strategy may only be evaluated once")
    case_sets = {tuple(query.case for query in strategy.queries) for strategy in strategies}
    if len(case_sets) != 1:
        raise ValueError("every strategy must be evaluated on the same dataset cases")

    findings = [
        finding
        for strategy in strategies
        for query in strategy.queries
        for finding in _classify_query(query)
    ]
    deltas: list[StrategyDelta] = []
    if RetrievalMode.HYBRID in by_mode:
        comparison_findings, deltas = _compare_hybrid(by_mode, primary_metric, tolerance)
        findings.extend(comparison_findings)

    findings.sort(key=lambda finding: (finding.category.value, finding.case, finding.mode or ""))
    improvements = sorted(
        (delta for delta in deltas if delta.delta > tolerance),
        key=lambda delta: (-delta.delta, delta.case),
    )
    regressions = sorted(
        (delta for delta in deltas if delta.delta < -tolerance),
        key=lambda delta: (delta.delta, delta.case),
    )
    return FailureAnalysis(
        primary_metric=primary_metric,
        tolerance=tolerance,
        category_counts=dict(
            sorted(Counter(finding.category.value for finding in findings).items())
        ),
        findings=findings,
        top_improvements=improvements[:highlight_limit],
        top_regressions=regressions[:highlight_limit],
    )


def _classify_query(query: QueryEvaluation) -> list[FailureFinding]:
    findings: list[FailureFinding] = []
    if not query.retrieved:
        findings.append(
            _finding(
                query,
                FailureCategory.NO_RESULTS,
                detail=f"{query.mode.value} returned no candidates",
            )
        )
    if query.missing_ids:
        findings.append(
            _finding(
                query,
                FailureCategory.MISSING_RELEVANT,
                entity_ids=query.missing_ids,
                detail=(
                    f"{len(query.missing_ids)} relevant artifact(s) absent from the "
                    f"{len(query.retrieved)} inspected {query.mode.value} results"
                ),
            )
        )
    if query.below_cutoff_ids:
        findings.append(
            _finding(
                query,
                FailureCategory.RANKED_BELOW_CUTOFF,
                entity_ids=query.below_cutoff_ids,
                detail=(
                    f"{len(query.below_cutoff_ids)} relevant artifact(s) retrieved but ranked "
                    f"below the top {query.k}"
                ),
            )
        )
    if query.first_relevant_rank is not None and query.first_relevant_rank > 1:
        findings.append(
            _finding(
                query,
                FailureCategory.TOP_RESULT_NOT_RELEVANT,
                entity_ids=[query.retrieved[0].id],
                detail=(
                    f"first relevant artifact ranked {query.first_relevant_rank} behind "
                    f"non-relevant {query.retrieved[0].id}"
                ),
            )
        )
    return findings


def _compare_hybrid(
    by_mode: dict[RetrievalMode, StrategyEvaluation],
    primary_metric: str,
    tolerance: float,
) -> tuple[list[FailureFinding], list[StrategyDelta]]:
    components = [mode for mode in _COMPONENT_MODES if mode in by_mode]
    if not components:
        return [], []

    findings: list[FailureFinding] = []
    deltas: list[StrategyDelta] = []
    hybrid_queries = {query.case: query for query in by_mode[RetrievalMode.HYBRID].queries}
    component_queries = {
        mode: {query.case: query for query in by_mode[mode].queries} for mode in components
    }

    for case, hybrid in hybrid_queries.items():
        scored = [
            (getattr(component_queries[mode][case].metrics, primary_metric), mode)
            for mode in components
        ]
        hybrid_score = getattr(hybrid.metrics, primary_metric)
        best_score, best_mode = max(scored, key=lambda item: (item[0], -components.index(item[1])))
        delta = hybrid_score - best_score
        deltas.append(
            StrategyDelta(
                case=case,
                query=hybrid.query,
                metric=primary_metric,
                hybrid_score=hybrid_score,
                best_component_mode=best_mode,
                best_component_score=best_score,
                delta=delta,
            )
        )
        if abs(delta) > tolerance:
            category = (
                FailureCategory.HYBRID_IMPROVED if delta > 0 else FailureCategory.HYBRID_REGRESSED
            )
            findings.append(
                _finding(
                    hybrid,
                    category,
                    compared_mode=best_mode,
                    metric_delta=delta,
                    detail=(
                        f"hybrid {primary_metric} {hybrid_score:.4f} versus best component "
                        f"{best_mode.value} {best_score:.4f}"
                    ),
                )
            )
        findings.extend(
            _channel_findings(hybrid, case, components, component_queries, delta, tolerance)
        )
    return findings, deltas


def _channel_findings(
    hybrid: QueryEvaluation,
    case: str,
    components: Sequence[RetrievalMode],
    component_queries: dict[RetrievalMode, dict[str, QueryEvaluation]],
    delta: float,
    tolerance: float,
) -> list[FailureFinding]:
    findings: list[FailureFinding] = []
    for mode, category in (
        (RetrievalMode.GRAPH, FailureCategory.GRAPH_HELPED),
        (RetrievalMode.SEMANTIC, FailureCategory.VECTOR_HELPED),
    ):
        if mode not in components:
            continue
        unique_relevant = sorted(
            component_queries[mode][case].relevant_ids_within(hybrid.k)
            - _other_relevant(case, components, component_queries, mode, hybrid.k)
        )
        contributed = [
            entity_id
            for entity_id in unique_relevant
            if entity_id in hybrid.relevant_ids_within(hybrid.k)
        ]
        if contributed:
            findings.append(
                _finding(
                    hybrid,
                    category,
                    compared_mode=mode,
                    entity_ids=contributed,
                    detail=(
                        f"{mode.value} was the only strategy retrieving {', '.join(contributed)} "
                        f"within the top {hybrid.k}, and hybrid kept it"
                    ),
                )
            )

    if RetrievalMode.GRAPH in components:
        graph_query = component_queries[RetrievalMode.GRAPH][case]
        relevant = set(hybrid.relevant_ids)
        graph_only_noise = sorted(
            {artifact.id for artifact in graph_query.retrieved[: hybrid.k]}
            - _other_retrieved(case, components, component_queries, RetrievalMode.GRAPH, hybrid.k)
            - relevant
        )
        promoted = [
            artifact.id
            for artifact in hybrid.retrieved[: hybrid.k]
            if artifact.id in graph_only_noise
        ]
        if promoted and delta < -tolerance:
            findings.append(
                _finding(
                    hybrid,
                    FailureCategory.GRAPH_HURT,
                    compared_mode=RetrievalMode.GRAPH,
                    entity_ids=promoted,
                    metric_delta=delta,
                    detail=(
                        f"hybrid promoted graph-only non-relevant {', '.join(promoted)} while "
                        "scoring below the best component strategy"
                    ),
                )
            )
    return findings


def _other_relevant(
    case: str,
    components: Sequence[RetrievalMode],
    component_queries: dict[RetrievalMode, dict[str, QueryEvaluation]],
    exclude: RetrievalMode,
    limit: int,
) -> set[str]:
    return {
        entity_id
        for mode in components
        if mode is not exclude
        for entity_id in component_queries[mode][case].relevant_ids_within(limit)
    }


def _other_retrieved(
    case: str,
    components: Sequence[RetrievalMode],
    component_queries: dict[RetrievalMode, dict[str, QueryEvaluation]],
    exclude: RetrievalMode,
    limit: int,
) -> set[str]:
    return {
        artifact.id
        for mode in components
        if mode is not exclude
        for artifact in component_queries[mode][case].retrieved[:limit]
    }


def _finding(
    query: QueryEvaluation,
    category: FailureCategory,
    *,
    compared_mode: RetrievalMode | None = None,
    entity_ids: Sequence[str] = (),
    metric_delta: float | None = None,
    detail: str,
) -> FailureFinding:
    return FailureFinding(
        case=query.case,
        query=query.query,
        category=category,
        mode=query.mode,
        compared_mode=compared_mode,
        entity_ids=list(entity_ids),
        metric_delta=metric_delta,
        detail=detail,
    )
