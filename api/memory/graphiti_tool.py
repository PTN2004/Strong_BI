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
        self.memory_name = f"{user_id}_memory"
        graph = GraphDatabaseFactory.create()
        
        if graph.db_type == "neo4j":
            from graphiti_core.driver.neo4j_driver import Neo4jDriver
            self._db = Neo4jDriver(
                
            )