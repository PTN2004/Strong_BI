"""Module to handle the graph data loading and schema retrieval."""

import asyncio
import json
import logging
from itertools import combinations
from typing import Any, Dict, List, Tuple

from litellm import acompletion  # BẮT BUỘC: Dùng bản bất đồng bộ
from pydantic import BaseModel

from api.config import Config

logger = logging.getLogger(__name__)

# --- PYDANTIC MODELS (Giữ nguyên) ---
class TableDescription(BaseModel):
    name: str
    description: str

class ColumnDescription(BaseModel):
    name: str
    description: str

class Descriptions(BaseModel):
    tables_descriptions: list[TableDescription]
    columns_descriptions: list[ColumnDescription]

# --- SCHEMA RETRIEVER CLASS ---
class SchemaRetriever:
    """
    Công cụ trích xuất Cấu trúc CSDL (Schema) bằng Vector Search.
    Đã được tối ưu 100% Đa hình cho Neo4j và FalkorDB.
    """
    def __init__(self, db, graph_id: str):
        self._db = db
        self.graph_id = graph_id

    async def get_db_description(self) -> Tuple[str, str]:
        """Lấy mô tả của DB an toàn trên mọi hạ tầng."""
        query = "MATCH (d:Database) RETURN d.description AS description, d.url AS url LIMIT 1"
        records = await self._db.query(query)
        
        if records:
            first_row = records[0]
            if isinstance(first_row, dict):
                return (first_row.get("description", "No description"), first_row.get("url", "No URL"))
            elif isinstance(first_row, (list, tuple)) and len(first_row) >= 2:
                return (first_row[0] or "No description", first_row[1] or "No URL")
                
        return ("No description available for this database.", "No URL available for this database.")

    async def _find_tables(self, embeddings: List[List[float]]) -> List[List[Any]]:
        """Tìm Table bằng Vector Search (Có rẽ nhánh DB)."""
        results = []
        for embedding in embeddings:
            if self._db.db_type == "falkordb":
                query = """
                    CALL db.idx.vector.queryNodes('Table','embedding',3,vecf32($embedding))
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(columns)
                    RETURN node.name AS name, node.description AS desc, node.foreign_keys AS fks, collect({
                        columnName: columns.name, description: columns.description,
                        dataType: columns.type, keyType: columns.key, nullable: columns.nullable
                    }) AS cols
                """
            else: # neo4j
                query = """
                    CALL db.index.vector.queryNodes('Table_embedding_index', 3, $embedding)
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(columns)
                    RETURN node.name AS name, node.description AS desc, node.foreign_keys AS fks, collect({
                        columnName: columns.name, description: columns.description,
                        dataType: columns.type, keyType: columns.key, nullable: columns.nullable
                    }) AS cols
                """
            
            records = await self._db.query(query, {"embedding": embedding})
            results.extend(self._format_to_list(records))
        return results

    async def _find_tables_by_columns(self, embeddings: List[List[float]]) -> List[List[Any]]:
        """Tìm Table thông qua Vector Search của Column."""
        results = []
        for embedding in embeddings:
            if self._db.db_type == "falkordb":
                query = """
                    CALL db.idx.vector.queryNodes('Column','embedding',3,vecf32($embedding))
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(table)-[:BELONGS_TO]-(columns)
                    RETURN table.name AS name, table.description AS desc, table.foreign_keys AS fks, collect({
                        columnName: columns.name, description: columns.description,
                        dataType: columns.type, keyType: columns.key, nullable: columns.nullable
                    }) AS cols
                """
            else: # neo4j
                query = """
                    CALL db.index.vector.queryNodes('Column_embedding_index', 3, $embedding)
                    YIELD node, score
                    MATCH (node)-[:BELONGS_TO]-(table)-[:BELONGS_TO]-(columns)
                    RETURN table.name AS name, table.description AS desc, table.foreign_keys AS fks, collect({
                        columnName: columns.name, description: columns.description,
                        dataType: columns.type, keyType: columns.key, nullable: columns.nullable
                    }) AS cols
                """
            records = await self._db.query(query, {"embedding": embedding})
            results.extend(self._format_to_list(records))
        return results

    async def _find_tables_sphere(self, tables: List[str]) -> List[List[Any]]:
        """Tìm các Table có quan hệ FK với các Table đã tìm được."""
        query = """
            MATCH (node:Table {name: $name})
            MATCH (node)-[:BELONGS_TO]-(column)-[:REFERENCES]-()-[:BELONGS_TO]-(table_ref)
            WITH table_ref
            MATCH (table_ref)-[:BELONGS_TO]-(columns)
            RETURN table_ref.name AS name, table_ref.description AS desc, table_ref.foreign_keys AS fks,
                   collect({
                       columnName: columns.name, description: columns.description,
                       dataType: columns.type, keyType: columns.key, nullable: columns.nullable
                   }) AS cols
        """
        results = []
        for name in tables:
            records = await self._db.query(query, {"name": name})
            results.extend(self._format_to_list(records))
        return results

    async def _find_connecting_tables(self, table_names: List[str]) -> List[List[Any]]:
        """Tìm các Table trung gian (Junction tables) bằng ShortestPath."""
        pairs = [list(pair) for pair in combinations(table_names, 2)]
        if not pairs:
            return []

        query = """
        UNWIND $pairs AS pair
        MATCH (a:Table {name: pair[0]})
        MATCH (b:Table {name: pair[1]})
        WITH a, b
        MATCH p = allShortestPaths((a)-[*..6]-(b))
        UNWIND nodes(p) AS path_node
        WITH DISTINCT path_node
        WHERE 'Table' IN labels(path_node) OR ('Column' IN labels(path_node) AND path_node.key_type = 'PRI')
        WITH path_node,
             'Table' IN labels(path_node) AS is_table,
             'Column' IN labels(path_node) AND path_node.key_type = 'PRI' AS is_pri_column
        OPTIONAL MATCH (path_node)-[:BELONGS_TO]->(parent_table:Table) WHERE is_pri_column
        WITH CASE WHEN is_table THEN path_node WHEN is_pri_column THEN parent_table ELSE null END AS target_table
        WHERE target_table IS NOT NULL
        WITH DISTINCT target_table
        MATCH (col:Column)-[:BELONGS_TO]->(target_table)
        RETURN target_table.name AS name, target_table.description AS desc, target_table.foreign_keys AS fks,
             collect({
                columnName: col.name, description: col.description,
                dataType: col.type, keyType: col.key, nullable: col.nullable
             }) AS cols
        """
        records = await self._db.query(query, {"pairs": pairs})
        return self._format_to_list(records)

    def _format_to_list(self, records: List[Any]) -> List[List[Any]]:
        """Helper để chuẩn hóa output về mảng 4 chiều cho tương thích với code cũ."""
        formatted = []
        if not records:
            return formatted
        for row in records:
            if isinstance(row, dict):
                formatted.append([row.get("name"), row.get("desc"), row.get("fks"), row.get("cols")])
            elif isinstance(row, (list, tuple)) and len(row) >= 4:
                formatted.append(list(row))
        return formatted

    def _get_unique_tables(self, tables_list: List[List[Any]]) -> List[List[Any]]:
        """Lọc trùng lặp các bảng tìm được."""
        unique_tables = {}
        for table_info in tables_list:
            if not table_info or len(table_info) < 4:
                continue
            table_name = table_info[0]
            if table_name not in unique_tables:
                try:
                    table_info[3] = [dict(od) for od in table_info[3]]
                    # Sửa lỗi cộng chuỗi nếu fks là None
                    fks = table_info[2] if table_info[2] else "None"
                    table_info[2] = f"Foreign keys: {fks}"
                    unique_tables[table_name] = table_info
                except Exception as e:
                    logger.error(f"Lỗi chuẩn hóa bảng {table_name}: {e}")
        return list(unique_tables.values())

    async def find(self, queries_history: List[str], db_description: str = None) -> List[List[Any]]:
        """Luồng chính: Đọc câu hỏi -> Gọi LLM -> Vector Search -> Trả về Schema."""
        user_query = queries_history[-1]
        previous_queries = queries_history[:-1]

        logger.info("Calling Async LLM to find relevant tables/columns for query")

        # 1. Gọi LLM BẤT ĐỒNG BỘ để không treo Server
        completion_result = await acompletion(
            model=Config.COMPLETION_MODEL,
            response_format=Descriptions,
            messages=[
                {
                    "role": "system",
                    "content": Config.FIND_SYSTEM_PROMPT.format(db_description=db_description or "")
                },
                {"role": "user", "content": json.dumps({"previous_user_queries": previous_queries, "user_query": user_query})},
            ],
            temperature=0,
        )

        json_data = json.loads(completion_result.choices[0].message.content)
        descriptions = Descriptions(**json_data)
        
        descriptions_text = ([desc.description for desc in descriptions.tables_descriptions] +
                             [desc.description for desc in descriptions.columns_descriptions])
        if not descriptions_text:
            return []

        # 2. Embedding text
        embedding_results = Config.EMBEDDING_MODEL.embed(descriptions_text)

        table_embeddings = embedding_results[:len(descriptions.tables_descriptions)]
        column_embeddings = embedding_results[len(descriptions.tables_descriptions):]

        # 3. Tìm kiếm Vector song song
        main_tasks = []
        if table_embeddings:
            main_tasks.append(self._find_tables(table_embeddings))
        if column_embeddings:
            main_tasks.append(self._find_tables_by_columns(column_embeddings))

        results = await asyncio.gather(*main_tasks)
        
        tables_des = results[0] if table_embeddings else []
        tables_by_columns_des = results[1] if (table_embeddings and column_embeddings) else (results[0] if not table_embeddings and column_embeddings else [])

        found_table_names = [t[0] for t in (tables_des + tables_by_columns_des) if t and len(t) > 0]
        found_table_names = list(set(found_table_names)) # Lọc trùng tên trước khi đi tìm Sphere

        # 4. Tìm kiếm Node lân cận (Path Traversal) song song
        if found_table_names:
            tables_by_sphere, tables_by_route = await asyncio.gather(
                self._find_tables_sphere(found_table_names),
                self._find_connecting_tables(found_table_names)
            )
        else:
            tables_by_sphere, tables_by_route = [], []

        # 5. Tổng hợp và trả về
        all_tables = tables_des + tables_by_columns_des + tables_by_route + tables_by_sphere
        return self._get_unique_tables(all_tables)