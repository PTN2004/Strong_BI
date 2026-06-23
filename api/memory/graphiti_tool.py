import os
import asyncio
import uuid
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from redis import Redis

from litellm import completion
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
            self.memory_name = f"{user_id}_memory"
            graph_driver = FalkorDriver(
                host=self._db.host,
                port=self._db.port,
                database=self.memory_name
            )

        self.graphiti_client = create_graphiti_client(graph_driver)
        self.memory_enabled = self.graphiti_client is not None
        
        self.user_id = user_id
        self.graph_id = graph_id
        
    async def _refresh_ttl(self) -> None:
        if self.MEMORY_TTL_SECONDS is None:
            return

        try:
            if self._db.db_type == "falkordb":
                from redis import RedisError
                try:
                    await self._db._client.execute_command("EXPIRE", self.memory_name, self.MEMORY_TTL_SECONDS)
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
    
    async def _ensure_entity_nodes_direct(self, user_id: str, database_name: str) -> bool:
        try:
            vector_syntax = self._db.format_vector("embedding")
            
            user_node_name = f"{user_id}"
            check_user_query = "MATCH (n:Entity {name: $name}) RETURN n.uuid AS uuid LIMIT 1"
            
            user_check_result = await self._db.query(check_user_query, {"name": user_node_name})
            
            if not user_check_result:  
                user_uuid = str(uuid.uuid4())
                user_name_embedding = Config.EMBEDDING_MODEL.embed(user_node_name)[0]
                
                user_node_data = {
                    'uuid': user_uuid,
                    'name': user_node_name,
                    'group_id': '\\_',
                    'created_at': datetime.now().isoformat(),
                    'summary': 'The User is using StrongBi'
                }
                
                user_cypher = f"""
                    MERGE (n:Entity {{uuid: $node.uuid}})
                    SET n += $node
                    SET n.timestamp = timestamp()
                    SET n.name_embedding = {vector_syntax}
                    RETURN n.uuid AS uuid
                """
                
                await self._db.query(user_cypher, {
                    "node": user_node_data,
                    "embedding": user_name_embedding
                })
                logging.info("Created user entity node with UUID: %s", user_uuid)
            else:
                logging.info("User entity node already exists")
            
            database_node_name = f"Database {database_name}"
            check_database_query = "MATCH (n:Entity {name: $name}) RETURN n.uuid AS uuid LIMIT 1"
            
            database_check_result = await self._db.query(check_database_query, {"name": database_node_name})
            
            if not database_check_result:
                database_uuid = str(uuid.uuid4())
                database_name_embedding = Config.EMBEDDING_MODEL.embed(database_node_name)[0]
                
                database_node_data = {
                    'uuid': database_uuid,
                    'name': database_node_name,
                    'group_id': '\\_',
                    'created_at': datetime.now().isoformat(),
                    'summary': f'Database {database_name} available for querying by user {user_id}'
                }
                
                database_cypher = f"""
                    MERGE (n:Entity {{uuid: $node.uuid}})
                    SET n += $node
                    SET n.timestamp = timestamp()
                    SET n.name_embedding = {vector_syntax}
                    RETURN n.uuid AS uuid
                """
                
                await self._db.query(database_cypher, {
                    "node": database_node_data,
                    "embedding": database_name_embedding
                })
                logging.info("Created database entity node: %s with UUID: %s", database_node_name, database_uuid)
            else:
                logging.info("Database entity node already exists: %s", database_node_name)
            
            try:
                relationship_query = """
                    MATCH (user:Entity {name: $user_name})
                    MATCH (db:Entity {name: $database_name})
                    MERGE (user)-[r:HAS_DATABASE]->(db)
                    RETURN r
                """
                
                await self._db.query(relationship_query, {
                    "user_name": user_node_name,
                    "database_name": database_node_name
                })
                logging.info("Created HAS_DATABASE relationship between user and %s database", database_node_name)
            except Exception as rel_error:
                logging.error("Error creating HAS_DATABASE relationship: %s", rel_error)
            
            return True
            
        except Exception as e:
            logging.error("Error creating entity nodes directly: %s", e)
            return False
        
    async def update_user_information(self, conversation: Dict[str, Any], history: Tuple[List[str], List[str]]) -> bool:
        try:
            query_get = """
                MATCH (u:Entity {name: $user_id})
                RETURN u.summary AS summary
            """
            summary_result = await self._db.query(query_get, {"user_id": self.user_id})
            
            summary = ""
            if summary_result and len(summary_result) > 0:
                first_row = summary_result[0]
                if isinstance(first_row, dict):
                    summary = first_row.get("summary", "")
                else:
                    summary = first_row[0] if first_row[0] is not None else ""

            conv_text = ""
            conv_text += f"User: {conversation.get('question', '')}\n"
            if conversation.get('generated_sql'):
                conv_text += f"SQL: {conversation['generated_sql']}\n"
            if conversation.get('error'):
                conv_text += f"Error: {conversation['error']}\n"
            if conversation.get('answer'):
                conv_text += f"Assistant: {conversation['answer']}\n"

            prompt = f"""
                You are updating the personal memory of user.
                ### Inputs
                1. Existing user summary (overall + personal info):
                {summary}

                2. Latest Q&A conversational memory:
                {conv_text}

                ### Task
                - Produce a new user summary of his overall preferences and his personal information.
                - *Important*: Ensure that the summary contains any personal statements or preferences expressed by the user.
                - Preserve existing personal information, preferences, and tendencies from the old summary.
                - Integrate any **new insights** about the user’s interests, behaviors, or database usage patterns from the latest memory.
                - If new info refines or corrects older info, update accordingly.
                - Focus only on **overall and personal information** — do not include temporary query details.
                - Write in **factual third-person style**, suitable for storage as a user node in a graph.
                - Try to explicitly divide overall summary, usage preferences and personal information.

                ### Output
                An updated user summary.
                """

            # 4. Chuẩn bị Messages cho LLM
            if len(history[1]) == 0:
                messages = [{"role": "user", "content": prompt}]
            else:
                messages = []
                for query_hist, result_hist in zip(history[0], history[1]):
                    messages.append({"role": "user", "content": query_hist})
                    messages.append({"role": "assistant", "content": result_hist})
                messages.append({"role": "user", "content": prompt})

            response = completion(
                model=Config.COMPLETION_MODEL,
                messages=messages,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()

            query_set = """
                MATCH (u:Entity {name: $user_id})
                SET u.summary = $summary
                RETURN u.summary AS summary
            """
            await self._db.query(query_set, {
                "user_id": self.user_id, 
                "summary": content
            })
            
            return True
            
        except Exception as e:
            logging.error(f"Error updating user information: {e}")
            return False
        
    async def add_new_memory(self, conversation: Dict[str, Any], history: Tuple[List[str], List[str]]) -> bool:
        try:
            analysis = await self.summarize_conversation(conversation, history)
            database_summary = analysis.get("database_summary", "")

            add_episode_task = self.graphiti_client.add_episode(
                name=f"Database_Facts_{self.user_id}_{self.graph_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                episode_body=f"Database {self.graph_id}:\n{database_summary}",
                source=EpisodeType.message, 
                reference_time=datetime.now(),
                source_description=f"Graph-oriented facts about Database: {self.graph_id} from User: {self.user_id} interaction"
            )

            update_user_task = self.update_user_information(conversation, history=history)

            await asyncio.gather(add_episode_task, update_user_task)
            
            logging.info(f"Đã lưu thành công Ký ức kép cho User {self.user_id} và DB {self.graph_id}.")
            return True

        except Exception as e:
            logging.error(f"Lỗi khi thực thi add_new_memory: {e}")
            return False
        
    async def summarize_conversation(self, conversation: Dict[str, Any], history: Tuple[List[str], List[str]]) -> Dict[str, Any]:
        conv_text = f"User: {conversation.get('question', '')}\n"
        if conversation.get('generated_sql'):
            conv_text += f"SQL: {conversation['generated_sql']}\n"
        if conversation.get('error'):
            conv_text += f"Error: {conversation['error']}\n"
        if conversation.get('answer'):
            conv_text += f"Assistant: {conversation['answer']}\n"

        success_status = conversation.get('success', True)
        conv_text += f"Execution Status: {'Success' if success_status else 'Failed'}\n\n"

        prompt = f"""
                Rewrite the following QueryWeaver question-answer interaction into a 
                database-oriented conversational summary for database "{self.graph_id}".  

                ### Requirements
                - Always explicitly say: "{self.graph_id} database" (not just "{self.graph_id}").  
                - Always include the user id "{self.user_id}" in the summary.  
                - Capture the Q&A flow in natural, intuitive language (not just facts).
                - Include the full **relevant query results** in the output, summarizing key fields if necessary. 
                - Keep it concise (2–6 sentences).  
                - Emphasize schema, entities, and queries relevant to "{self.graph_id} database".  
                - If no relevant database context exists, return an empty string.  

                ### Input
                {conv_text}

                ### Output
                A conversational database-oriented summary mentioning both "{self.user_id}" and "{self.graph_id} database".
                """
        
        try:
            messages = []
            
            if history and len(history) == 2 and len(history[0]) > 0:
                for query_hist, result_hist in zip(history[0], history[1]):
                    messages.append({"role": "user", "content": query_hist})
                    messages.append({"role": "assistant", "content": result_hist})
            
            messages.append({"role": "user", "content": prompt})

            response = completion(
                model=Config.COMPLETION_MODEL,
                messages=messages,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            return {
                "database_summary": content
            }
            
        except Exception as e:
            logging.error(f"Error in LLM summarization: {e}")
            return {
                "database_summary": ""
            }
            
    async def save_query_memory(self, query: str, sql_query: str, success: bool, error: Optional[str] = None) -> bool:
        if not self.memory_enabled:
            return False
            
        try:
            database_node_name = f"Database {self.graph_id}"
            
            relationship_type = "SUCCESS" if success else "FAILED"
            
            embeddings = Config.EMBEDDING_MODEL.embed(query)[0]
            
            vector_syntax = self._db.format_vector("embedding")

            cypher_query = f"""
                MATCH (db:Entity {{name: $db_name}})
                
                MERGE (q:Query {{
                    user_query: $user_query,
                    sql_query: $sql_query
                }})
                ON CREATE SET
                    q.success = $success,
                    q.error = $error,
                    q.timestamp = timestamp(),
                    q.embeddings = {vector_syntax}
                
                MERGE (db)-[r:{relationship_type}]->(q)
                ON CREATE SET
                    r.timestamp = timestamp()
                    
                RETURN q.uuid AS query_uuid
            """
            
            params = {
                "db_name": database_node_name,
                "user_query": query,
                "sql_query": sql_query,
                "success": success,
                "error": error or "",
                "embedding": embeddings
            }

            result = await self._db.query(cypher_query, params)
            
            if not result:
                logging.warning(f"Not found Node Database '{database_node_name}' để lưu Memory.")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Error when save (query memory): {e}")
            return False
        
    
    async def retrieve_similar_queries(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.memory_enabled:
            return []
            
        try:
            query_embedding = Config.EMBEDDING_MODEL.embed(query)[0]

            similar_queries = await self._db.search_similar_nodes(
                database_name=self.graph_id,
                query_embedding=query_embedding,
                limit=limit
            )
            
            return similar_queries

        except Exception as e:
            logging.error(f"Not found vector (retrieve_similar_queries): {e}")
            return []
        
    async def search_user_summary(self, limit: int = 5) -> str:
        if not self.memory_enabled:
            return ""
        try:

            query = """
                    MATCH (e:Entity {name: $name})
                    RETURN e.summary AS summary
                    """
            result = await self._db.query(query, {"name": self.user_id})
            if result and len(result) > 0:
                first_row = result[0]
                if isinstance(first_row, dict):
                    return first_row.get("summary", "")
                    
                elif isinstance(first_row, (list, tuple)) and len(first_row) > 0:
                    return first_row[0] if first_row[0] is not None else ""

            return ""
            
        except Exception as e:
            logging.error("Error searching user node: %s", e)
            return ""
        
    async def extract_episode_from_rel(self, rel_result) -> List[str]:
        if not self.memory_enabled:
            return []

        try:
            episodes_uuids = getattr(rel_result, "episodes", [])
            if not episodes_uuids:
                return []

            cypher_query = """
                MATCH (e:Episodic)
                WHERE e.uuid IN $uuids
                RETURN e.content AS content
            """
            
            results = await self._db.query(cypher_query, {"uuids": episodes_uuids})

            episode_contents = []
            
            if results:
                for row in results:
                    content = None
                    if isinstance(row, dict):
                        content = row.get("content")
                    elif isinstance(row, (list, tuple)) and len(row) > 0:
                        content = row[0]
                    
                    if content:
                        episode_contents.append(content)

            return episode_contents

        except Exception as e:
            logging.error(f"Error when extracting episodes (extract_episode_from_rel): {e}")
            return []
        
    async def search_database_facts(self, query: str, limit: int = 5, episode_limit: int = 3) -> str:
        if not self.memory_enabled:
            return ""
            
        try:
            cypher_query = """
                MATCH (e:Entity {name: $name})
                RETURN e.uuid AS uuid
                LIMIT 1
            """
            db_node_name = f"Database {self.graph_id}"
            db_result = await self._db.query(cypher_query, {"name": db_node_name})
            
            center_node_uuid = ""
            if db_result and len(db_result) > 0:
                first_row = db_result[0]
                if isinstance(first_row, dict):
                    center_node_uuid = first_row.get("uuid", "")
                elif isinstance(first_row, (list, tuple)) and len(first_row) > 0:
                    center_node_uuid = first_row[0] if first_row[0] is not None else ""
                    
            if not center_node_uuid:
                logging.warning(f"Note found Node {db_node_name} để lấy Facts.")
                return ""
            reranked_results = await self.graphiti_client.search(
                query=query,
                center_node_uuid=center_node_uuid,
                num_results=limit
            )
        
            database_facts_text = []
            episodes_contents = []
            
            if reranked_results and len(reranked_results) > 0:
                logging.info(f"Đã tìm thấy lịch sử & Facts cho Database: {self.graph_id}")
            
                for i, result_item in enumerate(reranked_results, 1):
                    if getattr(result_item, 'source_node_uuid', None) != center_node_uuid and \
                       getattr(result_item, 'target_node_uuid', None) != center_node_uuid:
                        continue
                    
                    if len(episodes_contents) < episode_limit:
                        episodes_content = await self.extract_episode_from_rel(result_item)
                        if episodes_content:
                            episodes_contents.extend(episodes_content)
                        
                    fact_entry = getattr(result_item, 'fact', str(result_item))
                
                    time_info = []
                    if hasattr(result_item, 'valid_at') and result_item.valid_at:
                        time_info.append(f"Valid from: {result_item.valid_at}")
                    if hasattr(result_item, 'invalid_at') and result_item.invalid_at:
                        time_info.append(f"Valid until: {result_item.invalid_at}")
                    
                    if time_info:
                        fact_entry += f" ({', '.join(time_info)})"
                    
                    database_facts_text.append(fact_entry)
                
            facts = "\n".join(database_facts_text) if database_facts_text else ""
            episodes = "\n".join(episodes_contents) if episodes_contents else ""
            
            database_context = ""
            if episodes:
                database_context += f"Previous sessions:\n{episodes}\n\n"
            if facts:
                database_context += f"Facts:\n{facts}"
                
            return database_context.strip()

        except Exception as e:
            logging.error(f"Error when search database facts (search_database_facts): {e}")
            return ""
    
    async def search_memories(self, query: str, user_limit: int = 5, database_limit: int = 10) -> str:
        if not self.memory_enabled:
            return ""
            
        try:
            user_summary_task = self.search_user_summary(limit=user_limit)
            database_facts_task = self.search_database_facts(query=query, limit=database_limit)
            queries_task = self.retrieve_similar_queries(query=query, limit=5)
            
            user_summary, database_facts, similar_queries = await asyncio.gather(
                user_summary_task,
                database_facts_task,
                queries_task,
                return_exceptions=True
            )
            
            if isinstance(user_summary, Exception):
                logging.warning(f"Failed to retrieve user summary: {str(user_summary)}")
                user_summary = ""
                
            if isinstance(database_facts, Exception):
                logging.warning(f"Failed to retrieve database facts: {str(database_facts)}")
                database_facts = ""
                
            if isinstance(similar_queries, Exception):
                logging.warning(f"Failed to retrieve similar queries: {str(similar_queries)}")
                similar_queries = []
            
            memory_context = ""
            
            if user_summary:
                memory_context += f"(Personal preferences and information):\n{user_summary}\n\n"
            
            if database_facts:
                memory_context += f"{self.graph_id} INTERACTION HISTORY (Previous queries and learnings about this database):\n{database_facts}\n\n"

            if similar_queries:
                memory_context += "SIMILAR QUERIES HISTORY:\n"

                successful_queries = [q for q in similar_queries if q.get('success', False)]
                failed_queries = [q for q in similar_queries if not q.get('success', False)]

                if successful_queries:
                    memory_context += "\nSUCCESSFUL QUERIES (Learn from these patterns):\n"
                    for i, query_data in enumerate(successful_queries, 1):
                        memory_context += f"{i}. Query: \"{query_data.get('user_query', '')}\"\n"
                        memory_context += f"   Successful SQL: {query_data.get('sql_query', '')}\n\n"

                if failed_queries:
                    memory_context += "FAILED QUERIES (Avoid these patterns):\n"
                    for i, query_data in enumerate(failed_queries, 1):
                        memory_context += f"{i}. Query: \"{query_data.get('user_query', '')}\"\n"
                        memory_context += f"   Failed SQL: {query_data.get('sql_query', '')}\n"
                        error_msg = query_data.get('error')
                        if error_msg:
                            memory_context += f"   Error: {error_msg}\n"
                        memory_context += f"   AVOID this approach.\n\n"
                
                memory_context += "\n"

            return memory_context

        except Exception as e:
            logging.error(f"Critical error while compiling memory context in search_memories: {str(e)}")
            return ""
        
    async def clean_memory(self, size: int = 10000) -> int:
        """
        Clean up old memory nodes to prevent the graph from growing indefinitely.
        Safely protects the current user node and SQL Schema structures (Tables/Columns).
        """
        if not self.memory_enabled:
            return 0
            
        try:
            pinned_user_name = f"{self.user_id}"
            
            cypher_query = """
                MATCH (n)
                WHERE NOT (n:Entity AND n.name = $pinned_user)
                  AND NOT n:Table 
                  AND NOT n:Column
                WITH n ORDER BY coalesce(n.timestamp, 0) DESC
                SKIP $keep
                DETACH DELETE n
            """
            
            params = {
                "pinned_user": pinned_user_name,
                "keep": int(size)
            }
            
            await self._db.query(cypher_query, params)
            
            logging.info(f"Successfully cleaned up memory, keeping the latest {size} nodes for user {self.user_id}.")
            return 0
            
        except Exception as e:
            logging.error(f"Critical error executing memory cleanup (clean_memory): {str(e)}")
            return 0
        
class AzureOpenAIConfig:
    """Cấu hình an toàn cho Microsoft Azure OpenAI (Không Hardcode)."""
    
    def __init__(self):
        self.api_key = os.getenv('AZURE_API_KEY')
        self.endpoint = os.getenv('AZURE_API_BASE') 
        self.api_version = os.getenv('AZURE_API_VERSION', '2024-02-01')
        
        # Đọc từ biến môi trường chuẩn thay vì hardcode "gpt-4.1"
        self.model_choice = os.getenv('AZURE_LLM_MODEL', 'gpt-4o')  
        self.small_model = os.getenv('AZURE_SMALL_MODEL', 'gpt-4o-mini')
        
        self.embedding_model = extract_model_name(getattr(Config, 'EMBEDDING_MODEL_NAME', 'text-embedding-3-small'))
        
        self.llm_deployment = self.model_choice
        self.small_model_deployment = self.small_model
        self.embedding_deployment = self.embedding_model
        
        self.embedding_endpoint = os.getenv('AZURE_EMBEDDING_ENDPOINT', self.endpoint)

def get_azure_openai_clients():
    """Khởi tạo Client cho Azure."""
    config = AzureOpenAIConfig()
    
    if not config.endpoint or not config.api_key:
        raise ValueError("Thiếu biến môi trường AZURE_API_BASE hoặc AZURE_API_KEY")
    
    llm_client_azure = AsyncAzureOpenAI(
        api_key=config.api_key,
        api_version=config.api_version,
        azure_endpoint=config.endpoint,
    )

    embedding_client_azure = AsyncAzureOpenAI(
        api_key=config.api_key,
        api_version=config.api_version,
        azure_endpoint=config.embedding_endpoint,
    )

    return llm_client_azure, embedding_client_azure, config

def create_graphiti_client(graph_driver: Any) -> Optional[Graphiti]:
    try:
        azure_flag = getattr(Config, 'AZURE_FLAG', False)
        llm_provider = getattr(Config, 'LLM_PROVIDER', 'openai')
        
        if azure_flag:
            llm_client_azure, embedding_client_azure, config = get_azure_openai_clients()

            azure_llm_config = LLMConfig(
                small_model=config.small_model_deployment,
                model=config.llm_deployment,
            )

            return Graphiti(
                graph_driver=graph_driver, 
                llm_client=OpenAIClient(config=azure_llm_config, client=llm_client_azure),
                embedder=OpenAIEmbedder(
                    config=OpenAIEmbedderConfig(
                        embedding_model=config.embedding_deployment,
                        embedding_dim=1536
                    ),
                    client=embedding_client_azure,
                ),
                cross_encoder=OpenAIRerankerClient(
                    config=LLMConfig(model=azure_llm_config.small_model),
                    client=llm_client_azure,
                ),
            )
            
        elif llm_provider == "openai":
            embedding_model_name = extract_model_name(getattr(Config, 'EMBEDDING_MODEL_NAME', 'text-embedding-3-small'))

            return Graphiti(
                graph_driver=graph_driver, 
                embedder=OpenAIEmbedder(
                    config=OpenAIEmbedderConfig(
                        embedding_model=embedding_model_name,
                        embedding_dim=1536
                    )
                ),
            )
            
        else:
            logging.warning(f"Graphiti Memory hiện chỉ hỗ trợ OpenAI hoặc Azure. Provider hiện tại: {llm_provider}. Tính năng Memory sẽ bị vô hiệu hóa (Disabled).")
            return None
            
    except Exception as e:
        logging.error(f"Lỗi khi khởi tạo Graphiti Client: {e}")
        return None