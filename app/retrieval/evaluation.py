"""Information-retrieval metrics for checked-in relevance judgments."""

import math
import re
from collections.abc import Sequence
from statistics import fmean
from typing import Self

from pydantic import Field, model_validator

from app.models import RetrievalRequest
from app.models.domain import DomainModel


class EvaluationCase(DomainModel):
    name: str = Field(min_length=2)
    request: RetrievalRequest
    relevance: dict[str, int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_judgments(self) -> Self:
        invalid_ids = [
            entity_id
            for entity_id in self.relevance
            if re.fullmatch(r"^(REQ|CMP|RSK|TST)-\d{3}$", entity_id) is None
        ]
        if invalid_ids:
            raise ValueError("relevance judgments contain an invalid entity ID")
        if any(grade < 1 or grade > 3 for grade in self.relevance.values()):
            raise ValueError("relevance grades must be between 1 and 3")
        return self


class EvaluationDataset(DomainModel):
    name: str
    k: int = Field(ge=1, le=25)
    cases: list[EvaluationCase] = Field(min_length=1)


def metrics_at_k(ranked_ids: Sequence[str], relevance: dict[str, int], k: int) -> dict[str, float]:
    retrieved = list(ranked_ids[:k])
    relevant_ids = {entity_id for entity_id, grade in relevance.items() if grade > 0}
    hits = sum(entity_id in relevant_ids for entity_id in retrieved)
    reciprocal_rank = next(
        (
            1.0 / rank
            for rank, entity_id in enumerate(retrieved, start=1)
            if entity_id in relevant_ids
        ),
        0.0,
    )
    dcg = sum(
        (2 ** relevance.get(entity_id, 0) - 1) / math.log2(rank + 1)
        for rank, entity_id in enumerate(retrieved, start=1)
    )
    ideal_grades = sorted(relevance.values(), reverse=True)[:k]
    ideal_dcg = sum(
        (2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1)
    )
    return {
        "precision_at_k": hits / k,
        "recall_at_k": hits / len(relevant_ids),
        "mrr": reciprocal_rank,
        "ndcg_at_k": dcg / ideal_dcg if ideal_dcg else 0.0,
    }


def mean_metrics(rows: Sequence[dict[str, float]]) -> dict[str, float]:
    if not rows:
        raise ValueError("at least one metric row is required")
    return {key: fmean(row[key] for row in rows) for key in rows[0]}
