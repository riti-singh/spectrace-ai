"""Core domain models and dataset integrity validation."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

RequirementId = Annotated[str, StringConstraints(pattern=r"^REQ-\d{3}$")]
ComponentId = Annotated[str, StringConstraints(pattern=r"^CMP-\d{3}$")]
RiskId = Annotated[str, StringConstraints(pattern=r"^RSK-\d{3}$")]
TestCaseId = Annotated[str, StringConstraints(pattern=r"^TST-\d{3}$")]


class DomainModel(BaseModel):
    """Shared strict configuration for externally loaded domain data."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RequirementType(StrEnum):
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    INTERFACE = "interface"
    SAFETY = "safety"
    SECURITY = "security"
    RELIABILITY = "reliability"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VerificationMethod(StrEnum):
    TEST = "test"
    ANALYSIS = "analysis"
    INSPECTION = "inspection"
    DEMONSTRATION = "demonstration"


class RiskSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    AUTOMATED = "automated"


class Requirement(DomainModel):
    """A uniquely identifiable, normative system requirement."""

    id: RequirementId
    title: str = Field(min_length=3, max_length=120)
    normative_text: str = Field(min_length=15)
    requirement_type: RequirementType
    priority: Priority
    source_section: str = Field(min_length=2, max_length=80)
    verification_method: VerificationMethod
    component_ids: list[ComponentId] = Field(min_length=1)
    risk_ids: list[RiskId] = Field(default_factory=list)
    dependency_ids: list[RequirementId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_relationship_lists(self) -> Self:
        """Reject ambiguous duplicate links and self-dependencies."""

        for field_name in ("component_ids", "risk_ids", "dependency_ids"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        if self.id in self.dependency_ids:
            raise ValueError("a requirement cannot depend on itself")
        return self


class Component(DomainModel):
    id: ComponentId
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10)


class Risk(DomainModel):
    id: RiskId
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10)
    severity: RiskSeverity
    mitigation: str = Field(min_length=10)


class TestCase(DomainModel):
    id: TestCaseId
    title: str = Field(min_length=3, max_length=120)
    objective: str = Field(min_length=10)
    requirement_ids: list[RequirementId] = Field(min_length=1)
    status: TestStatus

    @model_validator(mode="after")
    def reject_duplicate_requirement_links(self) -> Self:
        if len(self.requirement_ids) != len(set(self.requirement_ids)):
            raise ValueError("requirement_ids must not contain duplicates")
        return self


class Dataset(DomainModel):
    """The complete repository payload, validated as one referentially sound unit."""

    requirements: list[Requirement]
    components: list[Component]
    risks: list[Risk]
    test_cases: list[TestCase]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        collections = {
            "requirement": self.requirements,
            "component": self.components,
            "risk": self.risks,
            "test case": self.test_cases,
        }
        for label, records in collections.items():
            ids = [record.id for record in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} ID")

        requirement_ids = {item.id for item in self.requirements}
        component_ids = {item.id for item in self.components}
        risk_ids = {item.id for item in self.risks}
        for requirement in self.requirements:
            self._ensure_known(
                requirement.component_ids, component_ids, requirement.id, "component"
            )
            self._ensure_known(requirement.risk_ids, risk_ids, requirement.id, "risk")
            self._ensure_known(
                requirement.dependency_ids, requirement_ids, requirement.id, "dependency"
            )
        for test_case in self.test_cases:
            self._ensure_known(
                test_case.requirement_ids, requirement_ids, test_case.id, "requirement"
            )
        return self

    @staticmethod
    def _ensure_known(
        references: list[str], known_ids: set[str], owner_id: str, reference_type: str
    ) -> None:
        missing = sorted(set(references) - known_ids)
        if missing:
            raise ValueError(
                f"{owner_id} contains unknown {reference_type} reference(s): {', '.join(missing)}"
            )


class TraceabilitySummary(DomainModel):
    total_requirements: int = Field(ge=0)
    covered_requirements: int = Field(ge=0)
    uncovered_requirements: int = Field(ge=0)
    coverage_percentage: float = Field(ge=0, le=100)
    requirements_by_priority: dict[Priority, int]
    requirements_by_type: dict[RequirementType, int]


class RequirementTraceability(DomainModel):
    requirement: Requirement
    test_cases: list[TestCase]
    direct_dependencies: list[Requirement]
    components: list[Component]
    risks: list[Risk]
