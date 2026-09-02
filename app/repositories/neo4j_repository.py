"""Neo4j-backed deterministic domain and graph repository."""

from collections.abc import Mapping, Sequence
from typing import Any

from neo4j import Driver, GraphDatabase, RoutingControl
from neo4j.exceptions import AuthError, DriverError, Neo4jError

from app.models import (
    Component,
    Dataset,
    GraphCounts,
    GraphEntityType,
    GraphNode,
    GraphPath,
    Requirement,
    Risk,
    TestCase,
)
from app.repositories.exceptions import (
    RepositoryConnectionError,
    RepositoryError,
    RepositoryQueryError,
)

MAX_PATH_DEPTH = 10

CONSTRAINT_QUERIES = (
    "CREATE CONSTRAINT requirement_id_unique IF NOT EXISTS "
    "FOR (node:Requirement) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT component_id_unique IF NOT EXISTS "
    "FOR (node:Component) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT risk_id_unique IF NOT EXISTS FOR (node:Risk) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT test_case_id_unique IF NOT EXISTS "
    "FOR (node:TestCase) REQUIRE node.id IS UNIQUE",
)

INDEX_QUERIES = (
    "CREATE INDEX requirement_priority_index IF NOT EXISTS "
    "FOR (node:Requirement) ON (node.priority)",
    "CREATE INDEX requirement_type_index IF NOT EXISTS "
    "FOR (node:Requirement) ON (node.requirement_type)",
    "CREATE INDEX component_name_index IF NOT EXISTS FOR (node:Component) ON (node.name)",
    "CREATE INDEX risk_severity_index IF NOT EXISTS FOR (node:Risk) ON (node.severity)",
    "CREATE INDEX test_case_status_index IF NOT EXISTS FOR (node:TestCase) ON (node.status)",
)

LIST_REQUIREMENTS_QUERY = """
MATCH (requirement:Requirement)
RETURN requirement {
    .*,
    component_ids: [(requirement)-[:APPLIES_TO]->(component:Component) | component.id],
    risk_ids: [(requirement)-[:ADDRESSES]->(risk:Risk) | risk.id],
    dependency_ids: [
        (requirement)-[:DEPENDS_ON]->(dependency:Requirement) | dependency.id
    ]
} AS entity
ORDER BY requirement.id
"""

GET_REQUIREMENT_QUERY = """
MATCH (requirement:Requirement {id: $requirement_id})
RETURN requirement {
    .*,
    component_ids: [(requirement)-[:APPLIES_TO]->(component:Component) | component.id],
    risk_ids: [(requirement)-[:ADDRESSES]->(risk:Risk) | risk.id],
    dependency_ids: [
        (requirement)-[:DEPENDS_ON]->(dependency:Requirement) | dependency.id
    ]
} AS entity
"""

LIST_COMPONENTS_QUERY = """
MATCH (component:Component)
RETURN component {.*} AS entity
ORDER BY component.id
"""

LIST_RISKS_QUERY = """
MATCH (risk:Risk)
RETURN risk {.*} AS entity
ORDER BY risk.id
"""

LIST_TEST_CASES_QUERY = """
MATCH (test_case:TestCase)
RETURN test_case {
    .*,
    requirement_ids: [
        (test_case)-[:VERIFIES]->(requirement:Requirement) | requirement.id
    ]
} AS entity
ORDER BY test_case.id
"""

TRANSITIVE_DEPENDENCIES_QUERY = """
MATCH path = (source:Requirement {id: $requirement_id})-[:DEPENDS_ON*1..10]->
    (dependency:Requirement)
WHERE length(path) <= $depth
RETURN DISTINCT dependency {
    .*,
    component_ids: [(dependency)-[:APPLIES_TO]->(component:Component) | component.id],
    risk_ids: [(dependency)-[:ADDRESSES]->(risk:Risk) | risk.id],
    dependency_ids: [
        (dependency)-[:DEPENDS_ON]->(direct_dependency:Requirement) | direct_dependency.id
    ]
} AS entity
ORDER BY dependency.id
"""

DOWNSTREAM_IMPACT_QUERY = """
MATCH path = (dependent:Requirement)-[:DEPENDS_ON*1..10]->
    (source:Requirement {id: $requirement_id})
WHERE length(path) <= $depth
RETURN DISTINCT dependent {
    .*,
    component_ids: [(dependent)-[:APPLIES_TO]->(component:Component) | component.id],
    risk_ids: [(dependent)-[:ADDRESSES]->(risk:Risk) | risk.id],
    dependency_ids: [
        (dependent)-[:DEPENDS_ON]->(dependency:Requirement) | dependency.id
    ]
} AS entity
ORDER BY dependent.id
"""

COMPONENTS_FOR_REQUIREMENT_QUERY = """
MATCH (:Requirement {id: $requirement_id})-[:APPLIES_TO]->(component:Component)
RETURN component {.*} AS entity
ORDER BY component.id
"""

REQUIREMENTS_FOR_COMPONENT_QUERY = """
MATCH (requirement:Requirement)-[:APPLIES_TO]->(:Component {id: $component_id})
RETURN requirement {
    .*,
    component_ids: [(requirement)-[:APPLIES_TO]->(component:Component) | component.id],
    risk_ids: [(requirement)-[:ADDRESSES]->(risk:Risk) | risk.id],
    dependency_ids: [
        (requirement)-[:DEPENDS_ON]->(dependency:Requirement) | dependency.id
    ]
} AS entity
ORDER BY requirement.id
"""

SHORTEST_PATH_QUERY = """
MATCH (source), (target)
WHERE source.id = $source_id AND target.id = $target_id
MATCH path = allShortestPaths((source)-[*1..10]-(target))
WITH path, [node IN nodes(path) | node.id] AS path_ids
ORDER BY path_ids
LIMIT 1
RETURN {
    nodes: [node IN nodes(path) | {id: node.id, entity_type: labels(node)[0]}],
    relationship_types: [edge IN relationships(path) | type(edge)]
} AS path
"""

SELF_PATH_QUERY = """
MATCH (node {id: $entity_id})
RETURN {
    nodes: [{id: node.id, entity_type: labels(node)[0]}],
    relationship_types: []
} AS path
"""

DEPENDENCY_CYCLES_QUERY = """
MATCH path = (requirement:Requirement)-[:DEPENDS_ON*1..10]->(requirement)
RETURN DISTINCT [node IN nodes(path) | node.id] AS cycle
ORDER BY cycle
"""

UNVERIFIED_RISKS_QUERY = """
MATCH (risk:Risk)
WHERE NOT EXISTS {
    MATCH (:TestCase)-[:VERIFIES]->(:Requirement)-[:ADDRESSES]->(risk)
}
RETURN risk {.*} AS entity
ORDER BY risk.id
"""

ORPHAN_NODES_QUERY = """
MATCH (node)
WHERE NOT EXISTS { MATCH (node)--() }
RETURN {id: node.id, entity_type: labels(node)[0]} AS entity
ORDER BY entity.entity_type, entity.id
"""

GRAPH_COUNTS_QUERY = """
CALL {
    MATCH (node)
    UNWIND labels(node) AS label
    WITH label, count(node) AS count
    RETURN collect([label, count]) AS node_pairs
}
CALL {
    MATCH ()-[edge]->()
    WITH type(edge) AS relationship_type, count(edge) AS count
    RETURN collect([relationship_type, count]) AS relationship_pairs
}
RETURN node_pairs, relationship_pairs
"""


class Neo4jRepository:
    """Persist and traverse Spectrace records using an explicitly selected Neo4j database."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str,
        *,
        driver: Driver | None = None,
        verify_connectivity: bool = True,
    ) -> None:
        self.database = database
        try:
            self._driver = driver or GraphDatabase.driver(uri, auth=(username, password))
        except DriverError as exc:
            raise RepositoryConnectionError("unable to configure the Neo4j driver") from exc
        self._owns_driver = driver is None
        try:
            if verify_connectivity:
                self.verify_connectivity()
        except RepositoryError:
            if self._owns_driver:
                self._driver.close()
            raise

    def close(self) -> None:
        if self._owns_driver:
            self._driver.close()

    def verify_connectivity(self) -> None:
        records = self._execute("RETURN 1 AS ok", write=False)
        if not records or records[0]["ok"] != 1:
            raise RepositoryConnectionError("Neo4j connectivity verification returned no result")

    def list_requirements(self) -> list[Requirement]:
        return [
            self._to_requirement(record["entity"])
            for record in self._execute(LIST_REQUIREMENTS_QUERY)
        ]

    def get_requirement(self, requirement_id: str) -> Requirement | None:
        records = self._execute(GET_REQUIREMENT_QUERY, {"requirement_id": requirement_id})
        return self._to_requirement(records[0]["entity"]) if records else None

    def list_components(self) -> list[Component]:
        return [
            Component.model_validate(dict(record["entity"]))
            for record in self._execute(LIST_COMPONENTS_QUERY)
        ]

    def list_risks(self) -> list[Risk]:
        return [
            Risk.model_validate(dict(record["entity"]))
            for record in self._execute(LIST_RISKS_QUERY)
        ]

    def list_test_cases(self) -> list[TestCase]:
        return [
            self._to_test_case(record["entity"]) for record in self._execute(LIST_TEST_CASES_QUERY)
        ]

    def transitive_dependencies(self, requirement_id: str, depth: int) -> list[Requirement]:
        return self._requirement_nodes(
            TRANSITIVE_DEPENDENCIES_QUERY,
            {"requirement_id": requirement_id, "depth": depth},
        )

    def downstream_impact(self, requirement_id: str, depth: int) -> list[Requirement]:
        return self._requirement_nodes(
            DOWNSTREAM_IMPACT_QUERY,
            {"requirement_id": requirement_id, "depth": depth},
        )

    def components_for_requirement(self, requirement_id: str) -> list[Component]:
        return [
            Component.model_validate(dict(record["entity"]))
            for record in self._execute(
                COMPONENTS_FOR_REQUIREMENT_QUERY, {"requirement_id": requirement_id}
            )
        ]

    def requirements_for_component(self, component_id: str) -> list[Requirement]:
        return self._requirement_nodes(
            REQUIREMENTS_FOR_COMPONENT_QUERY, {"component_id": component_id}
        )

    def shortest_path(self, source_id: str, target_id: str) -> GraphPath | None:
        if source_id == target_id:
            records = self._execute(SELF_PATH_QUERY, {"entity_id": source_id})
            return GraphPath.model_validate(dict(records[0]["path"])) if records else None
        records = self._execute(
            SHORTEST_PATH_QUERY, {"source_id": source_id, "target_id": target_id}
        )
        if not records or records[0]["path"] is None:
            return None
        return GraphPath.model_validate(dict(records[0]["path"]))

    def dependency_cycles(self) -> list[list[str]]:
        return [list(record["cycle"]) for record in self._execute(DEPENDENCY_CYCLES_QUERY)]

    def unverified_risks(self) -> list[Risk]:
        return [
            Risk.model_validate(dict(record["entity"]))
            for record in self._execute(UNVERIFIED_RISKS_QUERY)
        ]

    def orphan_nodes(self) -> list[GraphNode]:
        return [
            GraphNode.model_validate(dict(record["entity"]))
            for record in self._execute(ORPHAN_NODES_QUERY)
        ]

    def create_schema(self) -> None:
        for query in (*CONSTRAINT_QUERIES, *INDEX_QUERIES):
            self._execute(query, write=True)

    def seed_dataset(self, dataset: Dataset, *, reset: bool = False) -> GraphCounts:
        if reset:
            self.reset_graph()
        self.create_schema()
        self._upsert_nodes(dataset)
        self._upsert_relationships(dataset)
        return self.graph_counts()

    def reset_graph(self) -> None:
        """Delete all target-database graph data only when explicitly invoked."""

        self._execute("MATCH (node) DETACH DELETE node", write=True)

    def graph_counts(self) -> GraphCounts:
        record = self._execute(GRAPH_COUNTS_QUERY)[0]
        observed_nodes = dict(record["node_pairs"])
        observed_relationships = dict(record["relationship_pairs"])
        node_counts = {
            entity_type: int(observed_nodes.get(entity_type.value, 0))
            for entity_type in GraphEntityType
        }
        relationship_counts = {
            relationship_type: int(observed_relationships.get(relationship_type, 0))
            for relationship_type in ("DEPENDS_ON", "APPLIES_TO", "ADDRESSES", "VERIFIES")
        }
        return GraphCounts(nodes=node_counts, relationships=relationship_counts)

    def _upsert_nodes(self, dataset: Dataset) -> None:
        node_batches: Sequence[tuple[str, list[dict[str, Any]]]] = (
            (
                "UNWIND $rows AS row MERGE (node:Requirement {id: row.id}) SET node = row",
                [
                    item.model_dump(
                        mode="json", exclude={"component_ids", "risk_ids", "dependency_ids"}
                    )
                    for item in dataset.requirements
                ],
            ),
            (
                "UNWIND $rows AS row MERGE (node:Component {id: row.id}) SET node = row",
                [item.model_dump(mode="json") for item in dataset.components],
            ),
            (
                "UNWIND $rows AS row MERGE (node:Risk {id: row.id}) SET node = row",
                [item.model_dump(mode="json") for item in dataset.risks],
            ),
            (
                "UNWIND $rows AS row MERGE (node:TestCase {id: row.id}) SET node = row",
                [
                    item.model_dump(mode="json", exclude={"requirement_ids"})
                    for item in dataset.test_cases
                ],
            ),
        )
        for query, rows in node_batches:
            self._execute(query, {"rows": rows}, write=True)

    def _upsert_relationships(self, dataset: Dataset) -> None:
        relationship_batches = (
            (
                "UNWIND $rows AS row MATCH (source:Requirement {id: row.source_id}) "
                "MATCH (target:Requirement {id: row.target_id}) "
                "MERGE (source)-[:DEPENDS_ON]->(target)",
                [
                    {"source_id": requirement.id, "target_id": target_id}
                    for requirement in dataset.requirements
                    for target_id in requirement.dependency_ids
                ],
            ),
            (
                "UNWIND $rows AS row MATCH (source:Requirement {id: row.source_id}) "
                "MATCH (target:Component {id: row.target_id}) "
                "MERGE (source)-[:APPLIES_TO]->(target)",
                [
                    {"source_id": requirement.id, "target_id": target_id}
                    for requirement in dataset.requirements
                    for target_id in requirement.component_ids
                ],
            ),
            (
                "UNWIND $rows AS row MATCH (source:Requirement {id: row.source_id}) "
                "MATCH (target:Risk {id: row.target_id}) "
                "MERGE (source)-[:ADDRESSES]->(target)",
                [
                    {"source_id": requirement.id, "target_id": target_id}
                    for requirement in dataset.requirements
                    for target_id in requirement.risk_ids
                ],
            ),
            (
                "UNWIND $rows AS row MATCH (source:TestCase {id: row.source_id}) "
                "MATCH (target:Requirement {id: row.target_id}) "
                "MERGE (source)-[:VERIFIES]->(target)",
                [
                    {"source_id": test_case.id, "target_id": target_id}
                    for test_case in dataset.test_cases
                    for target_id in test_case.requirement_ids
                ],
            ),
        )
        for query, rows in relationship_batches:
            self._execute(query, {"rows": rows}, write=True)

    def _requirement_nodes(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[Requirement]:
        return [
            self._to_requirement(record["entity"]) for record in self._execute(query, parameters)
        ]

    @staticmethod
    def _to_requirement(entity: Mapping[str, Any]) -> Requirement:
        payload = dict(entity)
        for field in ("component_ids", "risk_ids", "dependency_ids"):
            payload[field] = sorted(payload.get(field, []))
        return Requirement.model_validate(payload)

    @staticmethod
    def _to_test_case(entity: Mapping[str, Any]) -> TestCase:
        payload = dict(entity)
        payload["requirement_ids"] = sorted(payload.get("requirement_ids", []))
        return TestCase.model_validate(payload)

    def _execute(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        write: bool = False,
    ) -> list[Any]:
        try:
            records, _, _ = self._driver.execute_query(
                query,
                parameters_=dict(parameters or {}),
                routing_=RoutingControl.WRITE if write else RoutingControl.READ,
                database_=self.database,
            )
            return list(records)
        except (DriverError, AuthError) as exc:
            raise RepositoryConnectionError(
                f"unable to connect to Neo4j database '{self.database}'"
            ) from exc
        except Neo4jError as exc:
            raise RepositoryQueryError(
                f"Neo4j operation failed for database '{self.database}'"
            ) from exc
