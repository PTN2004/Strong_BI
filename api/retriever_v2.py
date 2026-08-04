import asyncio
import json
import logging
from itertools import combinations
from typing import Any, Dict, List, Tuple

from litellm import acompletion
from pydantic import BaseModel

from api.config import Config
from api.core.db_resolver import resolver_db
from api.agents.utils import filter_thinking_process

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


class TableDescription(BaseModel):
    name: str
    description: str


class ColumnDescription(BaseModel):
    name: str
    description: str


class Descriptions(BaseModel):
    tables_descriptions: list[TableDescription]
    columns_descriptions: list[ColumnDescription]


class Retriever:
    def __init__(self, graph_id: str, db=None):
        self._db = resolver_db(db)
        self._db.select_graph(graph_id)
        self.graph_id = graph_id

    async def get_db_description(self) -> Tuple[str, str]:

        query_result = await self._db.query(
            """
            MATCH (d:Database)
            RETURN d.description AS description, d.url AS url
            """
        )

        if not query_result.result_set:
            return ("No description available for this database.",
                    "No URL available for this database.")

        first_row = query_result.result_set[0]
        if isinstance(first_row, dict):
            return (first_row.get("description", ""), first_row.get("url", ""))
        elif isinstance(first_row, (list, tuple)) and len(first_row) >= 2:
            return (first_row[0] or "", first_row[1] or "")
        return ("", "")

    async def get_user_rules(self) -> str:
        query = """
            MATCH (d:Database)
            RETURN d.user_rules AS user_rules LIMIT 1
        """
        query_result = await self._db.query(query)

        if not query_result.result_set:
            return ""

        first_row = query_result.result_set[0]
        if isinstance(first_row, dict):
            return first_row.get("user_rules", "")
        elif isinstance(first_row, (list, tuple)) and len(first_row) > 0:
            return first_row[0] or ""
        return ""

    async def set_user_rules(graph_id: str, user_rules: str, db=None) -> None:
        graph = resolver_db(db)
        graph.select_graph(graph_id)
        await graph.query(
            """
            MERGE (d:Database)
            SET d.user_rules = $user_rules
            """,
            {"user_rules": user_rules}
        )

    async def _query_graph(self, query: str, params: Dict[str, Any] = None) -> List[List[Any]]:
        result = await self._db.query(query, params or {})
        formatted = []
        for row in result.result_set:
            if isinstance(row, dict):
                formatted.append([row.get("name"), row.get(
                    "description"), row.get("foreign_keys"), row.get("columns")])
            else:
                formatted.append(list(row))
        return formatted

    async def _find_tables(self, embeddings: List[List[float]]) -> List[List[Any]]:
        """Tìm kiếm Table dựa trên Vector ngữ nghĩa."""
        tasks = []
        for embedding in embeddings:
            if self._db.db_type == "falkordb":
                query = """
                    CALL db.idx.vector.queryNodes('Table','embedding',3,vecf32($embedding))
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(columns)
                    RETURN node.name AS name, node.description AS description, node.foreign_keys AS foreign_keys, collect({
                        columnName: columns.name, description: columns.description, dataType: columns.type, keyType: columns.key_type, nullable: columns.nullable
                    }) AS columns
                """
            else:
                query = """
                    CALL db.index.vector.queryNodes('Table_embedding_index', 3, $embedding)
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(columns)
                    RETURN node.name AS name, node.description AS description, node.foreign_keys AS foreign_keys, collect({
                        columnName: columns.name, description: columns.description, dataType: columns.type, keyType: columns.key_type, nullable: columns.nullable
                    }) AS columns
                """
            tasks.append(self._query_graph(query, {"embedding": embedding}))

        results = await asyncio.gather(*tasks)
        return [row for rows in results for row in rows]

    async def _find_tables_by_columns(self, embeddings: List[List[float]]) -> List[List[Any]]:
        """Tìm kiếm Table thông qua Vector ngữ nghĩa của Column."""
        tasks = []
        for embedding in embeddings:
            if self._db.db_type == "falkordb":
                query = """
                    CALL db.idx.vector.queryNodes('Column','embedding',3,vecf32($embedding))
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(table)-[:BELONGS_TO]-(columns)
                    RETURN table.name AS name, table.description AS description, table.foreign_keys AS foreign_keys, collect({
                        columnName: columns.name, description: columns.description, dataType: columns.type, keyType: columns.key_type, nullable: columns.nullable
                    }) AS columns
                """
            else:
                query = """
                    CALL db.index.vector.queryNodes('Column_embedding_index', 3, $embedding)
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(table)-[:BELONGS_TO]-(columns)
                    RETURN table.name AS name, table.description AS description, table.foreign_keys AS foreign_keys, collect({
                        columnName: columns.name, description: columns.description, dataType: columns.type, keyType: columns.key_type, nullable: columns.nullable
                    }) AS columns
                """
            tasks.append(self._query_graph(query, {"embedding": embedding}))

        results = await asyncio.gather(*tasks)
        return [row for rows in results for row in rows]



    async def _find_connecting_tables(self, table_names: List[str]) -> List[List[Any]]:
        """Thuật toán tìm kiếm các bảng bắc cầu trung gian (Junction Tables)."""
        pairs = [list(pair) for pair in combinations(table_names, 2)]
        if not pairs:
            return []

        query = """
        UNWIND $pairs AS pair
        MATCH (a:Table {name: pair[0]})
        MATCH (b:Table {name: pair[1]})
        WITH a, b
        MATCH p = allShortestPaths((a)-[:BELONGS_TO|REFERENCES*1..6]-(b))
        UNWIND nodes(p) AS path_node
        WITH DISTINCT path_node
        WHERE 'Table' IN labels(path_node) OR ('Column' IN labels(path_node) AND path_node.key_type = 'PRI')
        WITH path_node, 'Table' IN labels(path_node) AS is_table, 'Column' IN labels(path_node) AND path_node.key_type = 'PRI' AS is_pri_column
        OPTIONAL MATCH (path_node)-[:BELONGS_TO]->(parent_table:Table) WHERE is_pri_column
        WITH CASE WHEN is_table THEN path_node WHEN is_pri_column THEN parent_table ELSE null END AS target_table
        WHERE target_table IS NOT NULL
        WITH DISTINCT target_table
        MATCH (col:Column)-[:BELONGS_TO]->(target_table)
        RETURN target_table.name AS name, target_table.description AS description, target_table.foreign_keys AS foreign_keys,
             collect({
                columnName: col.name, description: col.description, dataType: col.type, keyType: col.key_type, nullable: col.nullable
             }) AS columns
        """
        try:
            return await self._query_graph(query, {"pairs": pairs})
        except Exception as e:
            logger.error(f"Error finding connecting tables: {e}")
            return []

    def _get_unique_tables(self, tables_list: List[List[Any]]) -> List[List[Any]]:
        unique_tables = {}
        for table_info in tables_list:
            if not table_info or len(table_info) < 4:
                continue

            table_name = table_info[0]
            try:
                if table_name not in unique_tables:
                    table_info[3] = [dict(od) for od in table_info[3]]
                    fks = table_info[2] if table_info[2] else "None"
                    table_info[2] = f"Foreign keys: {fks}"
                    unique_tables[table_name] = table_info
            except Exception as e:
                logger.error(f"Error deduplicating table {table_name}: {e}")

        return list(unique_tables.values())

    async def find(self, queries_history: List[str], db_description: str = None, custom_api_key: str = None, custom_model: str = None, custom_api_base: str = None) -> List[List[Any]]:
        user_query = queries_history[-1]
        previous_queries = queries_history[:-1]

        logger.info(
            "Calling Async LLM via SchemaRetriever to find relevant tables/columns"
        )
        
        model = custom_model or Config.COMPLETION_MODEL
        kwargs = {"temperature": 0, "timeout": 45}
        if custom_api_key:
            kwargs["api_key"] = custom_api_key
        if custom_api_base:
            kwargs["api_base"] = custom_api_base

        try:
            completion_result = await acompletion(
                model=model,
                response_format=Descriptions,
                messages=[
                    {"role": "system", "content": Config.FIND_SYSTEM_PROMPT.format(
                        db_description=db_description or "")},
                    {"role": "user", "content": json.dumps(
                        {"previous_user_queries": previous_queries, "user_query": user_query})},
                ],
                **kwargs
            )
            
            raw_content = completion_result.choices[0].message.content
            clean_content = filter_thinking_process(raw_content)
            json_data = json.loads(clean_content)
            descriptions = Descriptions(**json_data)
        except Exception as e:
            logger.error(f"Error calling LLM in Retriever: {e}")
            return []
            
        descriptions_text = ([desc.description for desc in descriptions.tables_descriptions] +
                             [desc.description for desc in descriptions.columns_descriptions])
        
        descriptions_text.append(user_query)
        
        if not descriptions_text:
            return []

        embedding_results = Config.EMBEDDING_MODEL.embed(descriptions_text)
        
        # Extract the embedding for the raw user query
        query_embedding = [embedding_results.pop()]

        table_embeddings = embedding_results[:len(
            descriptions.tables_descriptions)] + query_embedding
        column_embeddings = embedding_results[len(
            descriptions.tables_descriptions):] + query_embedding

        main_tasks = []
        if table_embeddings:
            main_tasks.append(self._find_tables(table_embeddings))
        if column_embeddings:
            main_tasks.append(self._find_tables_by_columns(column_embeddings))

        results = await asyncio.gather(*main_tasks)

        tables_des = results[0] if table_embeddings else []
        tables_by_columns_des = results[1] if (table_embeddings and column_embeddings) else (
            results[0] if not table_embeddings and column_embeddings else [])

        found_table_names = [t[0] for t in (
            tables_des + tables_by_columns_des) if t and len(t) > 0]
        found_table_names = list(set(found_table_names))

        if found_table_names:
            tables_by_route = await self._find_connecting_tables(found_table_names)
        else:
            tables_by_route = []

        all_tables = tables_des + tables_by_columns_des + tables_by_route
            
        unique_candidate_tables = self._get_unique_tables(all_tables)
        
        # Apply SchemaFilterAgent to prune redundant tables
        from api.agents.schema_filter_agent import SchemaFilterAgent
        filter_agent = SchemaFilterAgent(custom_api_key, custom_model, custom_api_base)
        selected_table_names = filter_agent.filter_tables(user_query, unique_candidate_tables)
        
        final_tables = [t for t in unique_candidate_tables if t[0] in selected_table_names]
        return final_tables
