import logging
from typing import Any, Dict, Optional

from falkordb import FalkorDB

from api.graph_db.graph_database import GraphDatabase

logger = logging.getLogger(__name__)


class FalkorDBGraphDatabase(GraphDatabase):
    def __init__(self, host: str = "localhost", port: int = 6379, db_index: int = 0):
        self.host = host
        self.port = port
        self.db_index = db_index
        self._client = None
        self._current_graph = None

    async def connect(self) -> None:
        try:
            self._client = FalkorDB(
                host=self.host, port=self.port, db=self.db_index)
            logger.info(f"Connected to FalkorDB at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to FalkorDB: {str(e)}")
            raise

    async def disconnect(self) -> None:
        if self._client:
            try:
                self._client.close()
                logger.info("Disconnected from FalkorDB")
            except Exception as e:
                logger.error(f"Error closing FalkorDB connection: {str(e)}")
            finally:
                self._client = None
                self._current_graph = None

    async def query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self._current_graph:
            raise RuntimeError("No graph selected. Call select_graph() first.")

        try:
            result = await self._current_graph.query(query, params or {})
            return result
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
        query = f"""
            CREATE VECTOR INDEX FOR (n:{node_label}) ON (n.{property_name})
            OPTIONS {{dimension:{dimension}, similarityFunction:'{similarity_function}'}}
        """
        try:
            await self.query(query)
            logger.info(
                f"Created vector index on {node_label}.{property_name} "
                f"(dimension={dimension}, similarity={similarity_function})"
            )
        except Exception as e:

            if "already exists" not in str(e).lower():
                logger.warning(f"Vector index creation warning: {str(e)}")

    async def create_index(self, node_label: str, property_name: str) -> None:
        query = f"CREATE INDEX FOR (n:{node_label}) ON (n.{property_name})"
        try:
            await self.query(query)
            logger.info(f"Created index on {node_label}.{property_name}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"Index creation warning: {str(e)}")

    def select_graph(self, graph_id: str):
        if not self._client:
            raise RuntimeError("Database not connected")
        
        self._current_graph = self._client.select_graph(graph_id)
        logger.info(f"Select database have id: {graph_id}")

    def is_connected(self) -> bool:
        return self._client is not None
    
    
    def format_vector(self, param_name):
        return f"vecf32(${param_name})"
    
    async def clear_database(self) -> None:
        if not self._current_graph:
            raise RuntimeError("No graph selected to delete.")
        
        try:
            await self._current_graph.delete()
            logger.info(f"FalkorDB: Deleted entire graph key '{self._current_graph.name}'")
        except Exception as e:
            logger.error(f"FalkorDB Error clearing database: {str(e)}")
            raise

    async def list_graph(self):
        if not self._client:
            raise RuntimeError("Database not connected")
        
        try:
            graphs = await self._client.list_graphs()
            return graphs if graphs else []
        
        except Exception as e:
            logger.error(f"Error retrieving graph list in FalkorDB: {str(e)}")
            raise

    @property
    def db_type(self) -> str:
        return "falkordb"

    @property
    def connection_string(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db_index}"
