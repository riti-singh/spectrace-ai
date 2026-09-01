# Spectrace AI

Spectrace AI is a production-oriented requirements traceability and test-planning API for a
fictional Asteria low-Earth-orbit satellite user terminal. Milestone 1 establishes a rigorous,
fully deterministic foundation: validated engineering records, referential-integrity checks, and
repeatable coverage analysis. It intentionally contains no LLM, LangGraph, GraphRAG, or Neo4j
integration.

## Architecture

```text
app/
├── api/             # FastAPI routes and HTTP contracts
├── core/            # Settings and dependency injection
├── models/          # Pydantic domain and response models
├── repositories/    # Storage contract and JSON implementation
├── services/        # Deterministic traceability calculations
└── main.py          # Application factory and ASGI entry point
data/
└── asteria_dataset.json
tests/               # Model, repository, service, and API tests
```

The API depends on the `DataRepository` protocol rather than a storage format. The
`JsonDataRepository` loads a single immutable snapshot and validates both individual records and
all cross-record references. `TraceabilityService` owns coverage and relationship calculations;
routes never open data files. FastAPI dependency providers connect these layers and allow isolated
replacement in tests or future storage migrations.

## Setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
uvicorn app.main:app --reload
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs` while the server is running.
Configuration uses the `SPECTRACE_` environment prefix. `SPECTRACE_DATA_FILE` selects another JSON
dataset, while the checked-in Asteria dataset is the default.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/requirements` | List validated requirements |
| GET | `/requirements/{requirement_id}` | Get one requirement |
| GET | `/components` | List system components |
| GET | `/risks` | List engineering risks |
| GET | `/test-cases` | List existing test cases |
| GET | `/traceability/summary` | Coverage totals and requirement distributions |
| GET | `/traceability/uncovered` | List requirements with no linked test case |
| GET | `/traceability/requirements/{requirement_id}` | Resolve tests, dependencies, components, and risks |

Examples:

```bash
curl http://127.0.0.1:8000/traceability/summary
curl http://127.0.0.1:8000/traceability/requirements/REQ-003
```

A missing, well-formed identifier returns a structured `404` response:

```json
{
  "detail": {
    "code": "requirement_not_found",
    "message": "Requirement 'REQ-999' was not found."
  }
}
```

## Synthetic dataset

The dataset contains 16 requirements, 7 components, 7 risks, and 9 existing test cases. It spans
satellite acquisition, active handoff, loss-of-link recovery, thermal protection, power management,
authentication, secure firmware updates, link adaptation, and emergency-service prioritization.
Dependency links capture direct prerequisites rather than inferred relationships.

Twelve requirements have at least one linked test case. Four are deliberately uncovered
(`REQ-008`, `REQ-012`, `REQ-013`, and `REQ-016`), producing a baseline coverage value of **75%**.
Draft test cases count as coverage because this milestone measures trace links, not execution or
pass/fail evidence.

## Quality checks

```bash
ruff check .
pytest --cov=app --cov-report=term-missing
git diff --check
```

GitHub Actions runs Ruff and pytest on every push and pull request, enforcing at least 90% statement
coverage for the application package.

## Current limitations

- JSON is a read-only, process-cached snapshot; there are no create/update/delete operations.
- Coverage means presence of a trace link and does not assess test status, quality, execution, or
  results.
- Dependencies are direct only; cycle detection and transitive impact analysis are not implemented.
- Authentication, authorization, persistence concurrency, pagination, and operational telemetry are
  outside this milestone.
- The Asteria content is synthetic engineering data and is not suitable for flight qualification.

## Roadmap

Future milestones can add a transactional persistence layer, Neo4j graph projections and GraphRAG,
LangGraph orchestration, human-reviewed AI test suggestions, dependency impact analysis, evidence
ingestion, role-based access, and production observability. Those capabilities should build on—and
remain testable against—the deterministic contracts introduced here.
