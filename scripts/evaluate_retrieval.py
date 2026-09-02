"""Evaluate every retrieval mode against checked-in synthetic judgments."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.core.config import PROJECT_ROOT, Settings
from app.models import RetrievalMode
from app.repositories import Neo4jRepository, RepositoryError
from app.retrieval.evaluation import EvaluationDataset, mean_metrics, metrics_at_k
from app.services.retrieval import RetrievalService


def evaluate(
    repository: Neo4jRepository, dataset: EvaluationDataset
) -> dict[str, dict[str, float]]:
    service = RetrievalService(repository)
    report: dict[str, dict[str, float]] = {}
    for mode in RetrievalMode:
        rows: list[dict[str, float]] = []
        for case in dataset.cases:
            request = case.request.model_copy(update={"mode": mode, "result_count": dataset.k})
            response = service.search(request)
            rows.append(
                metrics_at_k([item.id for item in response.results], case.relevance, dataset.k)
            )
        report[mode.value] = mean_metrics(rows)
    return report


def load_evaluation(path: Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data" / "retrieval_evaluation.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    if settings.repository_backend != "neo4j" or settings.neo4j_password is None:
        print("Evaluation requires the configured Neo4j backend.", file=sys.stderr)
        return 1
    try:
        dataset = load_evaluation(args.dataset)
        repository = Neo4jRepository(
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password.get_secret_value(),
            settings.neo4j_database,
        )
        try:
            report = evaluate(repository, dataset)
        finally:
            repository.close()
    except (OSError, ValidationError, RepositoryError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"dataset": dataset.name, "k": dataset.k, "modes": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
