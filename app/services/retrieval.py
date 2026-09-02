"""Deterministic rank fusion across lexical, semantic, and graph retrieval."""

import re
from collections.abc import Sequence

from app.models import (
    RetrievalCandidate,
    RetrievalExplanation,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
    ScoreComponent,
)
from app.repositories import RetrievalRepository
from app.retrieval import DeterministicSemanticEncoder

_ENTITY_ID_PATTERN = re.compile(r"\b(?:REQ|CMP|RSK|TST)-\d{3}\b", re.IGNORECASE)
_RRF_CONSTANT = 10
_HYBRID_WEIGHTS = {"lexical": 0.45, "semantic": 0.45, "graph": 0.10}


class RetrievalService:
    def __init__(
        self,
        repository: RetrievalRepository,
        encoder: DeterministicSemanticEncoder | None = None,
    ) -> None:
        self._repository = repository
        self._encoder = encoder or DeterministicSemanticEncoder()

    def search(self, request: RetrievalRequest) -> RetrievalResponse:
        entity_types = [value.value for value in request.entity_types]
        pool_size = min(100, max(20, request.result_count * 4))
        needs_seed_candidates = request.mode in {RetrievalMode.GRAPH, RetrievalMode.HYBRID}

        lexical = (
            self._repository.lexical_candidates(request.query, entity_types, pool_size)
            if request.mode in {RetrievalMode.LEXICAL, RetrievalMode.HYBRID}
            or needs_seed_candidates
            else []
        )
        semantic = (
            self._repository.semantic_candidates(
                self._encoder.encode(request.query), entity_types, pool_size
            )
            if request.mode in {RetrievalMode.SEMANTIC, RetrievalMode.HYBRID}
            or needs_seed_candidates
            else []
        )

        graph: list[RetrievalCandidate] = []
        if needs_seed_candidates:
            seed_ids = self._seed_ids(request.query, lexical, semantic)
            graph = self._repository.graph_candidates(
                seed_ids,
                entity_types,
                [value.value for value in request.relationships],
                request.graph_depth,
                pool_size,
            )

        channels = {"lexical": lexical, "semantic": semantic, "graph": graph}
        if request.mode is not RetrievalMode.HYBRID:
            selected = request.mode.value
            channels = {
                name: candidates if name == selected else []
                for name, candidates in channels.items()
            }
        results = self._fuse(channels, request.mode, request.result_count)
        return RetrievalResponse(
            query=request.query,
            mode=request.mode,
            result_count=len(results),
            results=results,
        )

    @staticmethod
    def _seed_ids(
        query: str,
        lexical: Sequence[RetrievalCandidate],
        semantic: Sequence[RetrievalCandidate],
    ) -> list[str]:
        seeds = [match.group(0).upper() for match in _ENTITY_ID_PATTERN.finditer(query)]
        seeds.extend(candidate.id for candidate in lexical[:3])
        seeds.extend(candidate.id for candidate in semantic[:3])
        return list(dict.fromkeys(seeds))[:8]

    @staticmethod
    def _fuse(
        channels: dict[str, list[RetrievalCandidate]],
        mode: RetrievalMode,
        limit: int,
    ) -> list[RetrievalResult]:
        candidate_by_id: dict[str, RetrievalCandidate] = {}
        components_by_id: dict[str, dict[str, ScoreComponent]] = {}
        for channel_name, candidates in channels.items():
            if not candidates:
                continue
            maximum = max(max(candidate.raw_score, 0.0) for candidate in candidates) or 1.0
            for rank, candidate in enumerate(candidates, start=1):
                candidate_by_id.setdefault(candidate.id, candidate)
                normalized = min(1.0, max(candidate.raw_score, 0.0) / maximum)
                contribution = (
                    _HYBRID_WEIGHTS[channel_name] / (_RRF_CONSTANT + rank)
                    if mode is RetrievalMode.HYBRID
                    else normalized
                )
                components_by_id.setdefault(candidate.id, {})[channel_name] = ScoreComponent(
                    raw_score=candidate.raw_score,
                    normalized_score=normalized,
                    rank=rank,
                    contribution=contribution,
                )

        scored = [
            (sum(component.contribution for component in components.values()), entity_id)
            for entity_id, components in components_by_id.items()
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        results: list[RetrievalResult] = []
        for score, entity_id in scored[:limit]:
            candidate = candidate_by_id[entity_id]
            components = components_by_id[entity_id]
            graph_candidate = next(
                (item for item in channels["graph"] if item.id == entity_id), None
            )
            results.append(
                RetrievalResult(
                    id=candidate.id,
                    entity_type=candidate.entity_type,
                    title=candidate.title,
                    text=candidate.text,
                    score=score,
                    explanation=RetrievalExplanation(
                        fusion_method=(
                            "weighted_reciprocal_rank_fusion_k_10"
                            if mode is RetrievalMode.HYBRID
                            else "normalized_component_score"
                        ),
                        lexical=components.get("lexical"),
                        semantic=components.get("semantic"),
                        graph=components.get("graph"),
                        graph_distance=(
                            graph_candidate.graph_distance if graph_candidate else None
                        ),
                        anchor_ids=graph_candidate.anchor_ids if graph_candidate else [],
                    ),
                )
            )
        return results
