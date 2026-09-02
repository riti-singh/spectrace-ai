"""Typed contracts for bounded, explainable hybrid retrieval."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.models.domain import DomainModel, GraphEntityType


class RetrievalMode(StrEnum):
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"
    HYBRID = "hybrid"


class GraphRelationshipType(StrEnum):
    DEPENDS_ON = "DEPENDS_ON"
    APPLIES_TO = "APPLIES_TO"
    ADDRESSES = "ADDRESSES"
    VERIFIES = "VERIFIES"


class RetrievalRequest(DomainModel):
    query: str = Field(min_length=2, max_length=500)
    mode: RetrievalMode = RetrievalMode.HYBRID
    entity_types: list[GraphEntityType] = Field(
        default_factory=lambda: list(GraphEntityType), min_length=1, max_length=4
    )
    relationships: list[GraphRelationshipType] = Field(
        default_factory=lambda: list(GraphRelationshipType), min_length=1, max_length=4
    )
    result_count: int = Field(default=10, ge=1, le=25)
    graph_depth: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def reject_duplicate_filters(self) -> Self:
        for field_name in ("entity_types", "relationships"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        return self


class RetrievalCandidate(DomainModel):
    """Repository-level candidate shared by each retrieval channel."""

    id: str = Field(pattern=r"^(REQ|CMP|RSK|TST)-\d{3}$")
    entity_type: GraphEntityType
    title: str
    text: str
    raw_score: float
    graph_distance: int | None = Field(default=None, ge=1, le=3)
    anchor_ids: list[str] = Field(default_factory=list)


class ScoreComponent(DomainModel):
    raw_score: float
    normalized_score: float = Field(ge=0, le=1)
    rank: int = Field(ge=1)
    contribution: float = Field(ge=0)


class RetrievalExplanation(DomainModel):
    fusion_method: str
    lexical: ScoreComponent | None = None
    semantic: ScoreComponent | None = None
    graph: ScoreComponent | None = None
    graph_distance: int | None = Field(default=None, ge=1, le=3)
    anchor_ids: list[str] = Field(default_factory=list)


class RetrievalResult(DomainModel):
    id: str = Field(pattern=r"^(REQ|CMP|RSK|TST)-\d{3}$")
    entity_type: GraphEntityType
    title: str
    text: str
    score: float = Field(ge=0)
    explanation: RetrievalExplanation


class RetrievalResponse(DomainModel):
    query: str
    mode: RetrievalMode
    result_count: int = Field(ge=0, le=25)
    results: list[RetrievalResult]


class RetrievalMetricSummary(DomainModel):
    mode: RetrievalMode
    precision_at_k: float = Field(ge=0, le=1)
    recall_at_k: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)
    ndcg_at_k: float = Field(ge=0, le=1)


class RetrievalEvaluationSummary(DomainModel):
    benchmark: str
    dataset: str
    query_count: int = Field(ge=1)
    k: int = Field(ge=1)
    characterization: str
    metrics: list[RetrievalMetricSummary]
