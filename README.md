# Spectrace AI

Spectrace AI is a production-oriented requirements traceability and test-planning API for a
fictional Asteria low-Earth-orbit satellite user terminal. Milestone 3 adds native Neo4j
full-text search, deterministic local vector embeddings, bounded graph expansion, and explainable
hybrid rank fusion while retaining both earlier backends and every existing API contract. The
source data, graph edges, embeddings, relevance judgments, and evaluation are reproducible and
require no hosted model or secret.

## Architecture

```text
                         ┌──────────────────────┐
HTTP / OpenAPI ─────────▶│ FastAPI route layer  │
                         └──────────┬───────────┘
                                    │ dependency injection
                         ┌──────────▼───────────┐
                         │ Traceability service │
                         │ Retrieval + WRRF     │
                         └──────────┬───────────┘
                                    │ typed repository protocols
                   ┌────────────────┴────────────────┐
          ┌────────▼─────────┐             ┌─────────▼─────────┐
          │ Validated JSON   │             │ Neo4j repository  │
          │ deterministic    │             │ full-text, vector │
          │ reference source │             │ and graph indexes │
          └──────────────────┘             └───────────────────┘
```

The application creates its selected repository lazily, reuses it for the app lifetime, and closes
the Neo4j driver during FastAPI shutdown. No driver is created globally at import time. Repository
failures are translated into domain-specific, structured API responses rather than exposing driver
details.

```text
app/
├── api/             # Existing routes plus graph and retrieval routes
├── core/            # Settings, backend selection, dependency injection, lifecycle
├── models/          # Strict domain, graph, and retrieval request/response models
├── repositories/    # JSON/Neo4j adapters, protocols, domain exceptions
├── retrieval/       # Local encoder and standard IR evaluation metrics
├── services/        # Traceability, graph, and deterministic rank fusion
└── main.py          # Application factory and ASGI app
data/                # Domain data and judged synthetic retrieval queries
scripts/             # Idempotent seeding and retrieval evaluation commands
tests/               # Unit, contract, API, and isolated Neo4j tests
```

## Graph schema

```text
(TestCase)-[:VERIFIES]->(Requirement)-[:APPLIES_TO]->(Component)
                                  │
                                  ├─[:DEPENDS_ON]─▶(Requirement)
                                  │
                                  └─[:ADDRESSES]──▶(Risk)
```

Every domain node also has the common `TraceEntity` label. Neo4j stores a generated `search_text`
property and a 256-dimensional normalized `embedding`; relationship ID arrays are reconstructed
from graph edges and are never duplicated as node properties. Public domain responses strip both
internal retrieval properties, preserving earlier JSON/Neo4j response parity.

| Label | Unique ID | Count |
|---|---:|---:|
| `Requirement` | `REQ-nnn` | 16 |
| `Component` | `CMP-nnn` | 7 |
| `Risk` | `RSK-nnn` | 7 |
| `TestCase` | `TST-nnn` | 9 |

| Relationship | Direction | Count |
|---|---|---:|
| `DEPENDS_ON` | Requirement → Requirement | 13 |
| `APPLIES_TO` | Requirement → Component | 39 |
| `ADDRESSES` | Requirement → Risk | 18 |
| `VERIFIES` | TestCase → Requirement | 12 |

Uniqueness constraints protect every domain ID. Secondary indexes cover requirement priority/type,
component name, risk severity, and test-case status. `trace_entity_fulltext` is a Lucene full-text
index and `trace_entity_embedding` is a cosine vector index over the common label.

## Retrieval design

`POST /retrieval/search` is available with the Neo4j backend. It retrieves bounded candidate pools
from three independent channels:

- lexical relevance from Neo4j full-text search with sanitized query tokens;
- semantic similarity from Neo4j vector search using a deterministic local concept/token/character
  feature encoder;
- graph proximity from one-to-three-hop undirected expansion around exact-ID and top search seeds.

Hybrid mode applies weighted reciprocal-rank fusion with `k=10`: lexical `0.45`, semantic `0.45`,
and graph `0.10`. Results are ordered by fused score and then entity ID. Each result exposes raw
score, within-channel normalized score, rank, contribution, graph distance, and graph anchors.
Entity types, relationship types, graph depth, query length, candidate pools, and returned results
are enum- or range-bounded; relationship names are never interpolated into Cypher.

## Backends

`SPECTRACE_REPOSITORY_BACKEND=json` is the safe default. It loads and validates the JSON dataset as
one referentially sound snapshot. All Milestone 1 endpoints work without external infrastructure.
Graph and retrieval endpoints return a structured `503` with code `neo4j_backend_required`, because
Neo4j-native index and traversal behavior is not silently simulated in memory.

`SPECTRACE_REPOSITORY_BACKEND=neo4j` makes graph relationships authoritative while preserving the
same domain models, ordering, coverage calculations, and existing API responses. Invalid backend
values fail settings validation immediately. A Neo4j password is mandatory for this mode.

## Setup

Python 3.11 or newer and, for graph development, Docker with Compose are required.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
```

Set a local password in the ignored `.env` file. Never commit that file.

```dotenv
SPECTRACE_REPOSITORY_BACKEND=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=choose-a-local-password
NEO4J_DATABASE=neo4j
```

Start Neo4j 5.26 LTS Community Edition and confirm the container is healthy:

```bash
docker compose up -d
docker compose ps
```

Neo4j Browser is available at [http://localhost:7474](http://localhost:7474). Bolt clients connect
to `bolt://localhost:7687`.

## Seed the graph

The seeder validates `data/asteria_dataset.json`, creates scalar/full-text/vector indexes with
`IF NOT EXISTS`, generates deterministic embeddings, uses `MERGE` for every node and edge, waits
for indexes to become online, and prints authoritative counts.

```bash
python -m scripts.seed_graph
python -m scripts.seed_graph        # same counts; no duplicates
```

Seeding is additive and never deletes graph data by default. For a disposable development database,
deletion must be explicitly authorized:

```bash
python -m scripts.seed_graph --reset
```

`--reset` executes `MATCH (node) DETACH DELETE node` against the configured database before
re-seeding. Do not use it against a database containing data you intend to retain.

Start the API after seeding:

```bash
uvicorn app.main:app --reload
```

OpenAPI documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## API

Milestone 1 contracts remain unchanged:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Application liveness |
| GET | `/requirements` | Requirements |
| GET | `/requirements/{requirement_id}` | One requirement |
| GET | `/components` | Components |
| GET | `/risks` | Risks |
| GET | `/test-cases` | Existing test cases |
| GET | `/traceability/summary` | Coverage and distributions |
| GET | `/traceability/uncovered` | Requirements without test links |
| GET | `/traceability/requirements/{requirement_id}` | Resolved deterministic traceability |

Neo4j-only graph endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/graph/health` | Neo4j connectivity/database check |
| GET | `/graph/requirements/{id}/dependencies?depth=5` | Transitive prerequisites |
| GET | `/graph/requirements/{id}/impact?depth=5` | Downstream dependents |
| GET | `/graph/requirements/{id}/components` | Connected components |
| GET | `/graph/path?source_id=...&target_id=...` | Deterministic shortest traceability path |
| GET | `/graph/cycles` | Dependency cycles |
| GET | `/graph/risks/unverified` | Risks without a TestCase→Requirement→Risk path |
| GET | `/graph/orphans` | Nodes with no relationships |

Neo4j-native retrieval:

| Method | Path | Purpose |
|---|---|---|
| POST | `/retrieval/search` | Lexical, semantic, graph, or explainable hybrid retrieval |

Examples:

```bash
curl "http://127.0.0.1:8000/graph/requirements/REQ-011/dependencies?depth=2"
curl "http://127.0.0.1:8000/graph/requirements/REQ-001/impact?depth=3"
curl "http://127.0.0.1:8000/graph/path?source_id=TST-003&target_id=RSK-002"
curl http://127.0.0.1:8000/graph/risks/unverified
```

```bash
curl -X POST http://127.0.0.1:8000/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "tampered firmware image recovery",
    "mode": "hybrid",
    "entity_types": ["Requirement", "TestCase", "Risk"],
    "relationships": ["DEPENDS_ON", "ADDRESSES", "VERIFIES"],
    "graph_depth": 2,
    "result_count": 5
  }'
```

Traversal depth is restricted to 1–10. Cypher queries use a static maximum of 10 hops and a
parameterized requested-depth filter, avoiding query-string construction from user input. Shortest
path ties are ordered by their node-ID sequence for deterministic output.

## Example Cypher

These read-only queries are useful in Neo4j Browser:

```cypher
MATCH (requirement:Requirement)-[edge]->(target)
RETURN requirement.id, type(edge), target.id
ORDER BY requirement.id, type(edge), target.id;
```

```cypher
MATCH path = (source:Requirement {id: 'REQ-011'})-[:DEPENDS_ON*1..10]->(dependency)
WHERE length(path) <= 2
RETURN DISTINCT dependency.id
ORDER BY dependency.id;
```

```cypher
MATCH (risk:Risk)
WHERE NOT EXISTS {
  MATCH (:TestCase)-[:VERIFIES]->(:Requirement)-[:ADDRESSES]->(risk)
}
RETURN risk.id, risk.title
ORDER BY risk.id;
```

Application code supplies all dynamic values as parameters and explicitly sets `database_` for every
driver query.

## Testing

Run deterministic unit/API/contract tests and the coverage gate without Neo4j:

```bash
ruff check .
ruff format --check .
pytest -m "not integration" --cov=app --cov-report=term-missing --cov-fail-under=90
git diff --check
```

Neo4j integration tests intentionally reset their target. They refuse to run unless both opt-in and
isolation confirmation are present. Use only a disposable database/container:

```bash
SPECTRACE_RUN_NEO4J_TESTS=1 \
SPECTRACE_NEO4J_TEST_ISOLATED=1 \
SPECTRACE_NEO4J_TEST_URI=bolt://localhost:7687 \
SPECTRACE_NEO4J_TEST_USERNAME=neo4j \
SPECTRACE_NEO4J_TEST_PASSWORD=your-test-password \
SPECTRACE_NEO4J_TEST_DATABASE=neo4j \
pytest -m integration
```

GitHub Actions starts a fresh Neo4j 5.26 Community service, runs Ruff, enforces the 90% application
coverage gate, and then runs the isolated integration suite. The suite proves idempotent counts,
repository contract parity, all traceability response parity, bounded traversal, impact, shortest
paths, cycles, unverified risks, orphan detection, native full-text/vector search, bounded retrieval
filters, deterministic fusion, and API parity. CI then reseeds and prints the evaluation report;
integration tests are run explicitly and are not counted as passing when skipped.

## Retrieval evaluation

`data/retrieval_evaluation.json` contains eight synthetic queries and graded relevant-result
judgments. The standard metrics implementation treats relevance greater than zero as a binary hit
for Precision@K, Recall@K, and MRR, and uses graded gains for nDCG@K. Run the production indexes:

```bash
python -m scripts.seed_graph --reset   # disposable database only
python -m scripts.evaluate_retrieval
```

Measured on the checked-in dataset with Neo4j Community 5.26.0 at `K=5`:

| Mode | Precision@5 | Recall@5 | MRR | nDCG@5 |
|---|---:|---:|---:|---:|
| Lexical | 0.6000 | 0.7625 | 0.8750 | 0.8232 |
| Semantic | 0.6250 | 0.7670 | 1.0000 | 0.8524 |
| Graph | 0.2250 | 0.2286 | 0.5000 | 0.1530 |
| Hybrid | 0.6500 | 0.7982 | 0.9375 | 0.8424 |

These are observed synthetic-benchmark results, not production relevance claims. Hybrid improves
Precision@5 and Recall@5; semantic-only is strongest for first-result rank and graded ordering on
this small corpus.

## Troubleshooting

- `NEO4J_PASSWORD is required`: set a non-empty password in the ignored `.env` file.
- `repository_unavailable`: confirm `docker compose ps` reports healthy and verify URI/credentials.
- `neo4j_backend_required`: select `SPECTRACE_REPOSITORY_BACKEND=neo4j` and seed the graph.
- Empty Neo4j results: run `python -m scripts.seed_graph`, then compare the printed counts above.
- Authentication failure after changing `.env`: the persistent volume retains the original password;
  use the original password or intentionally recreate the development volume.
- Integration tests refuse to start: provide both isolation flags and all `SPECTRACE_NEO4J_TEST_*`
  variables for a disposable database.

## Milestone 3 limitations

- Neo4j Community supports the configured single database; production tenancy/cluster concerns are
  not addressed.
- Traversals are deliberately bounded at 10 hops and dependency cycle searches report cycles only
  within that bound.
- Non-reset seeding is idempotent and additive. It does not remove relationships that were deleted
  from a later source dataset.
- Coverage still means a test-case trace link, not execution evidence, pass/fail state, or test
  quality.
- There are no write APIs, pagination, authentication/authorization, migrations, metrics, or tracing.
- The Asteria dataset is synthetic and not suitable for flight qualification.
- The local semantic encoder is deliberately compact and domain-normalized. It has no pretrained
  language understanding and should be replaced behind the encoder interface for a broader corpus.
- Graph-only retrieval is weak for free-text queries in the synthetic benchmark; it is most useful
  with explicit entity IDs or as bounded evidence in fusion.
- WRRF weights and `k` were selected for this small checked-in corpus and require validation before
  use on materially different data.
- There is no LLM, LangGraph orchestration, GraphRAG generation, or AI-authored engineering claim.

## Roadmap

The next milestone can add versioned graph migrations, evidence ingestion, stronger pluggable local
or hosted embeddings, and LangGraph orchestration with human review. Probabilistic components should
remain downstream of the validated repository contracts and retain deterministic evaluation fixtures
for every generated recommendation.
