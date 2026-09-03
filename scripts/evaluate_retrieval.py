"""Compare retrieval strategies and report failures against checked-in judgments.

Machine-readable JSON is written to stdout (or ``--json-out``); the concise human-readable
summary is written to stderr so the JSON stream stays pipeable.
"""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from app.core.config import PROJECT_ROOT, Settings
from app.models import RetrievalMode
from app.repositories import Neo4jRepository, RepositoryError
from app.retrieval.comparison import MetricScores
from app.retrieval.evaluation import EvaluationDataset
from app.retrieval.failure_analysis import DEFAULT_HIGHLIGHT_LIMIT, DEFAULT_PRIMARY_METRIC
from app.retrieval.report import (
    SUPPORTED_STRATEGIES,
    EvaluationReport,
    build_report,
    render_summary,
)
from app.services.retrieval import RetrievalService


def load_evaluation(path: Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data" / "retrieval_evaluation.json",
        help="judged evaluation dataset to run",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        type=RetrievalMode,
        choices=list(SUPPORTED_STRATEGIES),
        default=list(SUPPORTED_STRATEGIES),
        help="retrieval strategies to compare",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help="ranks to inspect per query; metrics are still scored at the dataset cutoff",
    )
    parser.add_argument(
        "--primary-metric",
        choices=sorted(MetricScores.model_fields),
        default=DEFAULT_PRIMARY_METRIC,
        help="metric used to compare hybrid against single strategies",
    )
    parser.add_argument(
        "--highlight-limit",
        type=int,
        default=DEFAULT_HIGHLIGHT_LIMIT,
        help="number of improvements and regressions to highlight",
    )
    parser.add_argument(
        "--no-latency",
        action="store_true",
        help="omit measured latency so the JSON output is byte-for-byte reproducible",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="write the JSON report to this path instead of stdout",
    )
    return parser


def run(args: argparse.Namespace, repository: Neo4jRepository) -> EvaluationReport:
    dataset = load_evaluation(args.dataset)
    service = RetrievalService(repository)
    return build_report(
        service.search,
        dataset,
        args.strategies,
        depth=args.depth,
        measure_latency=not args.no_latency,
        primary_metric=args.primary_metric,
        highlight_limit=args.highlight_limit,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    if settings.repository_backend != "neo4j" or settings.neo4j_password is None:
        print("Evaluation requires the configured Neo4j backend.", file=sys.stderr)
        return 1
    try:
        repository = Neo4jRepository(
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password.get_secret_value(),
            settings.neo4j_database,
        )
        try:
            report = run(args, repository)
        finally:
            repository.close()
    except (OSError, ValueError, ValidationError, RepositoryError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1

    payload = report.model_dump_json(indent=2)
    if args.json_out is None:
        print(payload)
    else:
        args.json_out.write_text(f"{payload}\n", encoding="utf-8")
        print(f"Wrote JSON report to {args.json_out}", file=sys.stderr)
    print(render_summary(report), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
