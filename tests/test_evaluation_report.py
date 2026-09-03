import json
from pathlib import Path

import pytest

from app.models import RetrievalCandidate, RetrievalMode
from app.retrieval.evaluation import EvaluationDataset
from app.retrieval.report import build_report, render_summary
from scripts.evaluate_retrieval import build_parser, load_evaluation, main, run
from tests.fakes import StubSearcher


class EmptyRetrievalRepository:
    """Repository double that indexes nothing, exercising the no-result path end to end."""

    def lexical_candidates(
        self, query: str, entity_types: list[str], limit: int
    ) -> list[RetrievalCandidate]:
        return []

    def semantic_candidates(
        self, embedding: list[float], entity_types: list[str], limit: int
    ) -> list[RetrievalCandidate]:
        return []

    def graph_candidates(
        self,
        seed_ids: list[str],
        entity_types: list[str],
        relationships: list[str],
        depth: int,
        limit: int,
    ) -> list[RetrievalCandidate]:
        return []


def test_report_combines_strategy_metrics_and_failure_analysis(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    report = build_report(stub_searcher, comparison_dataset, measure_latency=False)

    assert report.dataset == "stub-comparison"
    assert report.query_count == 3
    assert report.k == 2
    assert report.inspection_depth == 4
    assert [strategy.mode for strategy in report.strategies] == list(RetrievalMode)
    assert report.failure_analysis.category_counts["hybrid_regressed"] == 2
    assert json.loads(report.model_dump_json())["strategies"][0]["mode"] == "lexical"


def test_summary_lists_every_strategy_and_the_headline_deltas(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    report = build_report(stub_searcher, comparison_dataset, measure_latency=False)

    summary = render_summary(report)

    assert "Dataset: stub-comparison (queries=3, k=2, depth=4)" in summary
    assert all(mode.value in summary for mode in RetrievalMode)
    assert "graph_hurt" in summary
    assert "Top hybrid regressions:" in summary
    assert "gamma" in summary
    assert summary.count("-") > 0


def test_summary_reports_absent_findings_without_latency(
    stub_searcher: StubSearcher, comparison_dataset: EvaluationDataset
) -> None:
    report = build_report(
        stub_searcher,
        comparison_dataset,
        [RetrievalMode.HYBRID],
        measure_latency=False,
    )

    summary = render_summary(report)

    assert summary.count("  none") == 2
    assert "-" in summary.splitlines()[3]


def test_summary_reports_a_clean_run_without_findings(
    comparison_dataset: EvaluationDataset,
) -> None:
    perfect = StubSearcher(
        {
            (RetrievalMode.HYBRID, case.request.query): sorted(
                case.relevance, key=lambda entity_id: (-case.relevance[entity_id], entity_id)
            )
            for case in comparison_dataset.cases
        }
    )

    report = build_report(
        perfect, comparison_dataset, [RetrievalMode.HYBRID], measure_latency=False
    )

    assert report.failure_analysis.findings == []
    assert "  none" in render_summary(report)


def test_parser_defaults_and_strategy_selection() -> None:
    defaults = build_parser().parse_args([])
    selected = build_parser().parse_args(["--strategies", "semantic", "hybrid", "--depth", "6"])

    assert defaults.strategies == list(RetrievalMode)
    assert defaults.primary_metric == "ndcg_at_k"
    assert defaults.json_out is None
    assert selected.strategies == [RetrievalMode.SEMANTIC, RetrievalMode.HYBRID]
    assert selected.depth == 6


def test_run_evaluates_the_dataset_against_the_retrieval_service(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            {
                "name": "empty-index",
                "k": 3,
                "cases": [
                    {
                        "name": "case",
                        "request": {"query": "thermal shutdown"},
                        "relevance": {"REQ-005": 3},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    args = build_parser().parse_args(
        ["--dataset", str(dataset_path), "--strategies", "hybrid", "--no-latency"]
    )

    report = run(args, EmptyRetrievalRepository())  # type: ignore[arg-type]

    assert load_evaluation(dataset_path).name == "empty-index"
    assert report.strategies[0].queries[0].retrieved == []
    assert report.failure_analysis.category_counts == {"missing_relevant": 1, "no_results": 1}


def test_main_requires_the_neo4j_backend(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SPECTRACE_REPOSITORY_BACKEND", "json")

    assert main([]) == 1
    assert "requires the configured Neo4j backend" in capsys.readouterr().err
