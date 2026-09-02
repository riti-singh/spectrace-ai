"""Seed an Asteria dataset into Neo4j without duplicating nodes or relationships."""

import argparse
import sys
from pathlib import Path

from app.core.config import Settings
from app.models import GraphCounts
from app.repositories import (
    DatasetLoadError,
    Neo4jRepository,
    RepositoryError,
    load_dataset,
)


def seed_graph(settings: Settings, data_file: Path, *, reset: bool = False) -> GraphCounts:
    """Validate source data, seed it into Neo4j, and return authoritative graph counts."""

    if settings.neo4j_password is None or not settings.neo4j_password.get_secret_value():
        raise RepositoryError("NEO4J_PASSWORD must be set before seeding the graph")
    dataset = load_dataset(data_file.resolve())
    repository = Neo4jRepository(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )
    try:
        return repository.seed_dataset(dataset, reset=reset)
    finally:
        repository.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-file",
        type=Path,
        help="Validated JSON dataset to seed (defaults to SPECTRACE_DATA_FILE).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all data in the target database before seeding.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    data_file = args.data_file or settings.data_file
    try:
        counts = seed_graph(settings, data_file, reset=args.reset)
    except (DatasetLoadError, RepositoryError) as exc:
        print(f"Graph seeding failed: {exc}", file=sys.stderr)
        return 1

    print("Graph seed completed successfully.")
    print("Nodes:")
    for label, count in counts.nodes.items():
        print(f"  {label.value}: {count}")
    print("Relationships:")
    for relationship_type, count in counts.relationships.items():
        print(f"  {relationship_type}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
