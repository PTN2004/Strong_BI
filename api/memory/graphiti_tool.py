import os
import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from redis import Redis

from openai import AsyncAzureOpenAI
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client import OpenAIClient, LLMConfig
from graphiti_core.embedder import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder import OpenAIRerankerClient
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

from api.graph_db import GraphDatabaseFactory
from api.core.db_resolver import resolver_db
from api.config import Config

def extract_model_name(full_model_name:str) -> str:
    if '/' in full_model_name:
        return full_model_name.split('/', 1)[1]
    
    return full_model_name

class MemoryTool:
    MEMORY_TTL_SECONDS: Optional[int] = (
        int(os.environ["MEMORY_TTL_SECONDS"])
        if os.environ.get("MEMORY_TTL_SECONDS")
        else None
    )
    
    def __init__(self, user_id:str, graph_id:str, db=None):
        self._db = resolver_db(db)
        
        if self._db.db_type == "neo4j":
            from graphiti_core.driver.neo4j_driver import Neo4jDriver
            is_enterprise = getattr(self._db, "is_enterprise", False)
            
            if is_enterprise:
                self.memory_name = f"{user_id}_memory"
            else:
                self.memory_name = getattr(self._db, "_current_database", None) or getattr(self._db, "database", "neo4j")
            
            graph_driver = Neo4jDriver(
                uri=self._db.uri,
                username=self._db.username,
                password=self._db.password,
                database=self.memory_name
            )
        elif self._db.db_type == "falkordb":
            from graphiti_core.driver.falkordb_driver import FalkorDriver
            graph_driver = FalkorDriver(
                falkor_db=self._db,
                database=self.memory_name
            )

        self.graphiti_client = create_graphiti_client(graph_driver)
        self.memory_enable = self.graphiti_client is not None
        
        self.user_id = user_id
        self.graph_id = graph_id
        
    async def _refresh_ttl(self) -> None:
        if self.MEMORY_TTL_SECONDS is None:
            return

        try:
            if self._db.db_type == "falkordb":
                from redis import RedisError
                try:
                    await self._db._client.execute_command(
                        "EXPIRE", 
                        self.memory_name, 
                        self.MEMORY_TTL_SECONDS
                    )
                except RedisError as e:
                    logging.warning(f"Failed to refresh TTL for: {self.memory_name}: {e}")
                    
            elif self._db.db_type == "neo4j":
                pass
                
        except Exception as e:
            logging.warning(f"OS Error while setup TTL: {e}")
            
    @classmethod
    async def create(
        cls,
        user_id: str,
        graph_id: str,
        use_direct_entities: bool = True,
        db=None,
    ) -> "MemoryTool":  

        self = cls(user_id, graph_id, db=db)

        if not self.memory_enabled:
            return self

        await self._ensure_entity_nodes_direct(user_id, graph_id)

        vector_size = Config.EMBEDDING_MODEL.get_vector_size()
        
        await self._db.create_vector_index(
            node_label="Query",
            property_name="embeddings",
            dimension=vector_size,
            similarity_function="euclidean"
        )

        if self.MEMORY_TTL_SECONDS is not None:
            await self._refresh_ttl()

        return self