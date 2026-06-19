import logging
import os
from typing import Optional

from api.graph_db.graph_database import GraphDatabase

logger = logging.getLogger(__name__)


class GraphDatabaseFactory:

    @staticmethod
    def create() -> GraphDatabase:
        neo4j_url = os.getenv("NEO4J_URL", "").strip()
        if neo4j_url:
            return GraphDatabaseFactory._create_neo4j()

        return GraphDatabaseFactory._create_falkordb()

    @staticmethod
    def _create_neo4j() -> GraphDatabase:
        try:
            from api.graph_db.impl.neo4j import Neo4jGraphDatabase
        except ImportError as e:
            raise ImportError(
                "neo4j package is required for Neo4j support. "
                "Install it with: uv pip install neo4j"
            ) from e

        neo4j_url = os.getenv("NEO4J_URL")
        neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")

        if not neo4j_password:
            raise ValueError(
                "NEO4J_PASSWORD environment variable is required when using Neo4j"
            )

        logger.info(f"Creating Neo4j database connection: {neo4j_url}")
        return Neo4jGraphDatabase(
            uri=neo4j_url,
            username=neo4j_username,
            password=neo4j_password,
            database=neo4j_database,
        )

    @staticmethod
    def _create_falkordb() -> GraphDatabase:
        """Create a FalkorDB GraphDatabase instance."""
        try:
            from api.graph_db.impl.falkordb import FalkorDBGraphDatabase
        except ImportError as e:
            raise ImportError(
                "falkordb package is required for FalkorDB support. "
                "Install it with: uv pip install falkordb"
            ) from e

        falkordb_url = os.getenv("FALKORDB_URL", "").strip()
        if falkordb_url:
            host, port, db = GraphDatabaseFactory._parse_redis_url(
                falkordb_url)
        else:
            host = os.getenv("FALKORDB_HOST", "localhost")
            port = int(os.getenv("FALKORDB_PORT", "6379"))
            db = int(os.getenv("FALKORDB_DB", "0"))

        logger.info(f"Creating FalkorDB connection: {host}:{port}/{db}")
        return FalkorDBGraphDatabase(host=host, port=port, db_index=db)

    @staticmethod
    def _parse_redis_url(url: str) -> tuple[str, int, int]:
        try:
            if url.startswith("redis://"):
                url = url[8:]

            parts = url.split("/")
            if len(parts) < 1:
                raise ValueError("Invalid Redis URL format")

            db = int(parts[1]) if len(parts) > 1 else 0

            host_port = parts[0].split(":")
            if len(host_port) < 1:
                raise ValueError("Invalid host:port format")

            host = host_port[0] or "localhost"
            port = int(host_port[1]) if len(host_port) > 1 else 6379

            return host, port, db
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid Redis URL format: {url}") from e

    @staticmethod
    def get_db_type() -> str:
        neo4j_url = os.getenv("NEO4J_URL", "").strip()
        return "neo4j" if neo4j_url else "falkordb"
