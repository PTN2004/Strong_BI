import logging
from typing import List, Dict, Optional, Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from api.graph_db.graph_database import GraphDatabase, QueryDBResult


logger = logging.getLogger(__name__)


class Neo4jGraphDatabase(GraphDatabase):

    def __init__(
        self,
        uri: str,
        username: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
        is_enterprise: bool = False
    ):
        if not uri:
            raise ValueError("Neo4j URI is required")
        if not password:
            raise ValueError("Neo4j password is required")

        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self._driver: Optional[AsyncDriver] = None
        self._current_database = None
        self.is_enterprise = is_enterprise

    async def connect(self) -> None:
        try:
            self._driver = AsyncGraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password),
            )

            async with self._driver.session(database=self.database) as session:
                await session.run("RETURN 1")
            logger.info(
                f"Connected to Neo4j at {self.uri} (database: {self.database})")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise

    async def disconnect(self) -> None:
        if self._driver:
            try:
                await self._driver.close()
                logger.info("Disconnected from Neo4j")
            except Exception as e:
                logger.error(f"Error closing Neo4j connection: {str(e)}")
            finally:
                self._driver = None
                self._current_database = None

    async def query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryDBResult:
        if not self._driver:
            raise RuntimeError("Database not connected")

        if self.is_enterprise and self._current_database:
            target_db = self._current_database
        else:
            target_db = self.database

        try:
            records, summary, keys = await self._driver.execute_query(
                query,
                parameters_=params or {},
                database_=target_db
            )

            return QueryDBResult(
                result_set=[record.data() for record in records],
            )

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}\nQuery: {query}")
            raise

    async def create_vector_index(
        self,
        node_label: str,
        property_name: str,
        dimension: int,
        similarity_function: str = "euclidean",
    ) -> None:
        similarity_map = {
            "euclidean": "EUCLIDEAN",
            "cosine": "COSINE",
            "dot": "DOT_PRODUCT",
        }
        neo4j_similarity = similarity_map.get(
            similarity_function.lower(), "EUCLIDEAN")

        query = f"""
            CREATE VECTOR INDEX {node_label}_{property_name}_index IF NOT EXISTS
            FOR (n:{node_label})
            ON (n.{property_name})
            OPTIONS {{indexConfig: {{`vector.dimensions`: {dimension}, `vector.similarity_function`: '{neo4j_similarity}'}}}}
        """
        try:
            await self.query(query)
            logger.info(
                f"Created vector index on {node_label}.{property_name} "
                f"(dimension={dimension}, similarity={neo4j_similarity})"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"Vector index creation warning: {str(e)}")

    async def create_index(self, node_label: str, property_name: str) -> None:
        query = f"CREATE INDEX IF NOT EXISTS FOR (n:{node_label}) ON (n.{property_name})"
        try:
            await self.query(query)
            logger.info(f"Created index on {node_label}.{property_name}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"Index creation warning: {str(e)}")

    def is_connected(self) -> bool:
        return self._driver is not None

    def format_vector(self, param_name):
        return f"${param_name}"

    def select_graph(self, graph_id: str):
        if not self._driver:
            raise RuntimeError("Database not connected")
        self._current_database = graph_id
        logger.info(f"Select database have id: {graph_id}")

    async def clear_graph(self):
        try:
            await self.query("MATCH (n) DETACH DELETE n")
            logger.info(
                f"Neo4j: Cleared all nodes and relationships in database.")
        except Exception as e:
            logger.error(f"Neo4j Error clearing database: {str(e)}")
            raise

    async def list_graph(self) -> List[str]:
        if not self._driver:
            raise RuntimeError("Database not connect")
        if self.is_enterprise:
            try:
                async with self._driver.session(database="system") as session:
                    result = await session.run("SHOW DATABASES YIELD name")
                    record = await result.values()
                    graphs = [rec[0]
                              for rec in record if rec[0] not in ("system")]
                    return graphs

            except Exception as e:
                logger.error(f"Query execution failed: {str(e)}")
        else:
            return [self.database]

    async def search_similar_queries_by_uuid(self, db_uuid: str, embedding: list, limit: int = 5) -> list:
        cypher_query = """
            CALL db.index.vector.queryNodes('Query_embeddings_index', 10, $embedding)
            YIELD node, score
            MATCH (db:Entity {uuid: $db_uuid})-[r]->(node)
            RETURN node {
                .user_query,
                .sql_query,
                .success,
                .error
            } AS query
            ORDER BY score DESC
            LIMIT $limit
        """
        params = {"db_uuid": db_uuid, "embedding": embedding, "limit": limit}
        records = await self.query(cypher_query, params)

        similar_queries = []
        for record in records.result_set:
            if isinstance(record, (list, tuple)) and len(record) > 0:
                similar_queries.append(record[0])
            elif isinstance(record, dict):
                similar_queries.append(record.get("query"))
        return similar_queries

    @property
    def db_type(self) -> str:
        return "neo4j"

    @property
    def connection_string(self) -> str:
        return f"{self.uri}/{self.database}"
