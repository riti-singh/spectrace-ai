"""Domain-model validation tests."""

import pytest
from pydantic import ValidationError

from app.models import Requirement
from app.models import TestCase as DomainTestCase


def valid_requirement() -> dict[str, object]:
    return {
        "id": "REQ-100",
        "title": "Valid requirement",
        "normative_text": "The terminal shall perform a deterministic and verifiable behavior.",
        "requirement_type": "functional",
        "priority": "high",
        "source_section": "3.1 Test",
        "verification_method": "test",
        "component_ids": ["CMP-001"],
        "risk_ids": ["RSK-001"],
        "dependency_ids": ["REQ-001"],
    }


def test_requirement_accepts_valid_domain_values() -> None:
    requirement = Requirement.model_validate(valid_requirement())

    assert requirement.id == "REQ-100"
    assert requirement.priority.value == "high"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "requirement-100"),
        ("normative_text", "too short"),
        ("priority", "urgent"),
        ("verification_method", "guess"),
        ("component_ids", []),
    ],
)
def test_requirement_rejects_invalid_values(field: str, value: object) -> None:
    payload = valid_requirement()
    payload[field] = value

    with pytest.raises(ValidationError):
        Requirement.model_validate(payload)


def test_requirement_rejects_self_dependency() -> None:
    payload = valid_requirement()
    payload["dependency_ids"] = ["REQ-100"]

    with pytest.raises(ValidationError, match="cannot depend on itself"):
        Requirement.model_validate(payload)


def test_requirement_rejects_duplicate_relationships() -> None:
    payload = valid_requirement()
    payload["risk_ids"] = ["RSK-001", "RSK-001"]

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        Requirement.model_validate(payload)


def test_models_forbid_unknown_fields() -> None:
    payload = valid_requirement()
    payload["unplanned_field"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Requirement.model_validate(payload)


def test_test_case_rejects_duplicate_requirement_links() -> None:
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        DomainTestCase.model_validate(
            {
                "id": "TST-100",
                "title": "Duplicate link check",
                "objective": "Ensure each test relationship is represented only once.",
                "requirement_ids": ["REQ-001", "REQ-001"],
                "status": "draft",
            }
        )
