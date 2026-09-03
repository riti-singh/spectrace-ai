"""Assemble and render the strategy-comparison evaluation report."""

from collections.abc import Sequence

from pydantic import Field

from app.models import RetrievalMode
from app.models.domain import DomainModel
from app.retrieval.comparison import (
    Searcher,
    StrategyEvaluation,
    evaluate_strategies,
    inspection_depth,
)
from app.retrieval.evaluation import EvaluationDataset
from app.retrieval.failure_analysis import (
    DEFAULT_HIGHLIGHT_LIMIT,
    DEFAULT_PRIMARY_METRIC,
    DEFAULT_TOLERANCE,
    FailureAnalysis,
    analyze_failures,
)

SUPPORTED_STRATEGIES: tuple[RetrievalMode, ...] = tuple(RetrievalMode)


class EvaluationReport(DomainModel):
    dataset: str
    query_count: int = Field(ge=1)
    k: int = Field(ge=1)
    inspection_depth: int = Field(ge=1)
    strategies: list[StrategyEvaluation]
    failure_analysis: FailureAnalysis


def build_report(
    search: Searcher,
    dataset: EvaluationDataset,
    modes: Sequence[RetrievalMode] = SUPPORTED_STRATEGIES,
    *,
    depth: int | None = None,
    measure_latency: bool = True,
    primary_metric: str = DEFAULT_PRIMARY_METRIC,
    tolerance: float = DEFAULT_TOLERANCE,
    highlight_limit: int = DEFAULT_HIGHLIGHT_LIMIT,
) -> EvaluationReport:
    strategies = evaluate_strategies(
        search, dataset, modes, depth=depth, measure_latency=measure_latency
    )
    return EvaluationReport(
        dataset=dataset.name,
        query_count=len(dataset.cases),
        k=dataset.k,
        inspection_depth=inspection_depth(dataset, depth),
        strategies=strategies,
        failure_analysis=analyze_failures(
            strategies,
            primary_metric=primary_metric,
            tolerance=tolerance,
            highlight_limit=highlight_limit,
        ),
    )


def render_summary(report: EvaluationReport) -> str:
    """Render a concise, deterministic human-readable summary of the report."""

    k = report.k
    lines = [
        f"Dataset: {report.dataset} (queries={report.query_count}, k={k}, "
        f"depth={report.inspection_depth})",
        "",
        f"{'strategy':<10}{'P@K':>9}{'R@K':>9}{'MRR':>9}{'nDCG@K':>9}{'latency_ms':>13}",
    ]
    for strategy in report.strategies:
        latency = f"{strategy.mean_latency_ms:.1f}" if strategy.mean_latency_ms is not None else "-"
        lines.append(
            f"{strategy.mode.value:<10}"
            f"{strategy.metrics.precision_at_k:>9.4f}"
            f"{strategy.metrics.recall_at_k:>9.4f}"
            f"{strategy.metrics.mrr:>9.4f}"
            f"{strategy.metrics.ndcg_at_k:>9.4f}"
            f"{latency:>13}"
        )

    analysis = report.failure_analysis
    lines.extend(["", f"Failure categories (primary metric {analysis.primary_metric}):"])
    lines.extend(f"  {category:<24}{count}" for category, count in analysis.category_counts.items())
    if not analysis.category_counts:
        lines.append("  none")

    for title, deltas in (
        ("Top hybrid improvements", analysis.top_improvements),
        ("Top hybrid regressions", analysis.top_regressions),
    ):
        lines.extend(["", f"{title}:"])
        lines.extend(
            f"  {delta.delta:+.4f} {delta.case} "
            f"(hybrid {delta.hybrid_score:.4f} vs {delta.best_component_mode.value} "
            f"{delta.best_component_score:.4f})"
            for delta in deltas
        )
        if not deltas:
            lines.append("  none")
    return "\n".join(lines)
