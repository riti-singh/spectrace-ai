"""Assertions shared by deterministic repository implementations."""

from app.repositories import DataRepository


def assert_asteria_repository_contract(repository: DataRepository) -> None:
    requirements = repository.list_requirements()
    assert [item.id for item in requirements] == [f"REQ-{number:03d}" for number in range(1, 17)]
    assert repository.get_requirement("REQ-001") == requirements[0]
    assert repository.get_requirement("REQ-999") is None
    assert [item.id for item in repository.list_components()] == [
        f"CMP-{number:03d}" for number in range(1, 8)
    ]
    assert [item.id for item in repository.list_risks()] == [
        f"RSK-{number:03d}" for number in range(1, 8)
    ]
    assert [item.id for item in repository.list_test_cases()] == [
        f"TST-{number:03d}" for number in range(1, 10)
    ]
