import math

import pytest

from app.models import Requirement
from app.retrieval import EMBEDDING_DIMENSIONS, DeterministicSemanticEncoder
from app.retrieval.embedding import entity_search_document


def test_encoder_is_deterministic_normalized_and_concept_aware() -> None:
    encoder = DeterministicSemanticEncoder()

    credential = encoder.encode("credential")
    authentication = encoder.encode("authentication")

    assert credential == authentication
    assert len(credential) == EMBEDDING_DIMENSIONS
    assert math.sqrt(sum(value * value for value in credential)) == pytest.approx(1.0)
    assert encoder.encode("") == [0.0] * EMBEDDING_DIMENSIONS


def test_search_document_uses_public_scalar_fields(repository) -> None:
    requirement: Requirement = repository.get_requirement("REQ-001")  # type: ignore[assignment]

    document = entity_search_document(requirement)

    assert "REQ-001" in document
    assert requirement.title in document
    assert "CMP-001" not in document


def test_search_document_rejects_unknown_input() -> None:
    with pytest.raises(TypeError):
        entity_search_document(object())
