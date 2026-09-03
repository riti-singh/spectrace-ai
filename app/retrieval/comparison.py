"""Run one judged dataset against every supported retrieval strategy."""

import time
from collections.abc import Callable, Sequence
from statistics import fmean

from pydantic import Field

from app.models import RetrievalMode, RetrievalRequest, RetrievalResponse
from app.models.domain import DomainModel
from app.retrieval.evaluation import EvaluationDataset, mean_metrics, metrics_at_k

Searcher = Callable[[RetrievalRequest], RetrievalResponse]

MAX_RESULT_COUNT = 25


class MetricScores(DomainModel):
    """The metric set produced by :func:`app.retrieval.evaluation.metrics_at_k`."""

    precision_at_k: float = Field(ge=0, le=1)
    recall_at_k: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)
    ndcg_at_k: float = Field(ge=0, le=1)


class RetrievedArtifact(DomainModel):
    id: str = Field(pattern=r"^(REQ|CMP|RSK|TST)-\d{3}$")
    rank: int = Field(ge=1)
    score: float
    grade: int = Field(ge=0, le=3)


class QueryEvaluation(DomainModel):
    """Structured, replayable evidence for one query under one strategy."""

    case: str
    query: str
    mode: RetrievalMode
    k: int = Field(ge=1)
    relevant_ids: list[str]
    retrieved: list[RetrievedArtifact]
    missing_ids: list[str]
    below_cutoff_ids: list[str]
    first_relevant_rank: int | None = Field(default=None, ge=1)
    metrics: MetricScores
    latency_ms: float | None = Field(default=None, ge=0)

    @property
    def retrieved_ids(self) -> list[str]:
        return [artifact.id for artifact in self.retrieved]

    def relevant_ids_within(self, limit: int) -> set[str]:
        relevant = set(self.relevant_ids)
        return {artifact.id for artifact in self.retrieved[:limit] if artifact.id in relevant}


class StrategyEvaluation(DomainModel):
    mode: RetrievalMode
    metrics: MetricScores
    mean_latency_ms: float | None = Field(default=None, ge=0)
    queries: list[QueryEvaluation]


def inspection_depth(dataset: EvaluationDataset, depth: int | None = None) -> int:
    """Return how many ranked results to inspect while still scoring at ``dataset.k``."""

    resolved = depth or min(MAX_RESULT_COUNT, dataset.k * 2)
    if resolved < dataset.k:
        raise ValueError("inspection depth must be at least the dataset cutoff")
    return resolved


def evaluate_strategy(
    search: Searcher,
    dataset: EvaluationDataset,
    mode: RetrievalMode,
    *,
    depth: int | None = None,
    measure_latency: bool = True,
) -> StrategyEvaluation:
    """Evaluate one strategy, retrieving extra ranks but scoring at ``dataset.k``."""

    inspect_depth = inspection_depth(dataset, depth)

    queries: list[QueryEvaluation] = []
    for case in dataset.cases:
        request = case.request.model_copy(update={"mode": mode, "result_count": inspect_depth})
        started = time.perf_counter()
        response = search(request)
        elapsed_ms = (time.perf_counter() - started) * 1000 if measure_latency else None
        ranked_ids = [result.id for result in response.results]
        metrics = metrics_at_k(ranked_ids, case.relevance, dataset.k)
        relevant_ids = sorted(case.relevance)
        top_k_ids = set(ranked_ids[: dataset.k])
        queries.append(
            QueryEvaluation(
                case=case.name,
                query=case.request.query,
                mode=mode,
                k=dataset.k,
                relevant_ids=relevant_ids,
                retrieved=[
                    RetrievedArtifact(
                        id=result.id,
                        rank=rank,
                        score=result.score,
                        grade=case.relevance.get(result.id, 0),
                    )
                    for rank, result in enumerate(response.results, start=1)
                ],
                missing_ids=[
                    entity_id for entity_id in relevant_ids if entity_id not in ranked_ids
                ],
                below_cutoff_ids=[
                    entity_id
                    for entity_id in relevant_ids
                    if entity_id in ranked_ids and entity_id not in top_k_ids
                ],
                first_relevant_rank=next(
                    (
                        rank
                        for rank, entity_id in enumerate(ranked_ids[: dataset.k], start=1)
                        if entity_id in case.relevance
                    ),
                    None,
                ),
                metrics=MetricScores.model_validate(metrics),
                latency_ms=elapsed_ms,
            )
        )

    latencies = [query.latency_ms for query in queries if query.latency_ms is not None]
    return StrategyEvaluation(
        mode=mode,
        metrics=MetricScores.model_validate(
            mean_metrics([query.metrics.model_dump() for query in queries])
        ),
        mean_latency_ms=fmean(latencies) if latencies else None,
        queries=queries,
    )


def evaluate_strategies(
    search: Searcher,
    dataset: EvaluationDataset,
    modes: Sequence[RetrievalMode],
    *,
    depth: int | None = None,
    measure_latency: bool = True,
) -> list[StrategyEvaluation]:
    if not modes:
        raise ValueError("at least one retrieval strategy is required")
    return [
        evaluate_strategy(search, dataset, mode, depth=depth, measure_latency=measure_latency)
        for mode in dict.fromkeys(modes)
    ]
