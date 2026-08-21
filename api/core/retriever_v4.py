import asyncio
import logging
from typing import List, Dict, Any, Tuple

from api.config import Config
from api.core.db_resolver import resolver_db

logger = logging.getLogger(__name__)

class RetrieverV4:
    def __init__(self, graph_id: str, db=None):
        self._db = resolver_db(db)
        self._db.select_graph(graph_id)
        self.graph_id = graph_id

    async def _query_graph(self, query: str, params: Dict[str, Any] = None) -> List[Any]:
        result = await self._db.query(query, params or {})
        return result.result_set

    async def _vector_search(self, label: str, embedding: List[float], top_k: int = 3) -> List[Any]:
        if self._db.db_type == "falkordb":
            query = f"""
                CALL db.idx.vector.queryNodes('{label}','embedding',{top_k},vecf32($embedding))
                YIELD node, score
                RETURN node
            """
        else:
            query = f"""
                CALL db.index.vector.queryNodes('{label}_embedding_index', {top_k}, $embedding)
                YIELD node, score
                RETURN node
            """
        try:
            return await self._query_graph(query, {"embedding": embedding})
        except Exception as e:
            error_msg = str(e)
            if "no such vector schema index" not in error_msg.lower():
                logger.warning(f"Vector search failed for {label}: {e}")
            return []

    async def find_context(self, question: str) -> Tuple[str, Dict[str, Any]]:

        embedding_results = Config.EMBEDDING_MODEL.embed([question])
        if not embedding_results:
            return "No context found.", {"nodes": [], "edges": []}
        
        question_embedding = embedding_results[0]
        
        # Parallel vector searches across all relevant node types
        tasks = [
            self._vector_search("Metric", question_embedding, top_k=4),
            self._vector_search("Dimension", question_embedding, top_k=4),
            self._vector_search("Table", question_embedding, top_k=8),
            self._vector_search("Column", question_embedding, top_k=15)
        ]
        
        results = await asyncio.gather(*tasks)
        metrics = results[0]
        dimensions = results[1]
        tables = results[2]
        columns = results[3]
        
        # Extract direct table names from semantic nodes and found tables
        table_names = set()
        
        for t in tables:
            node = t[0] if isinstance(t, list) else t.get("node", {})
            if "name" in node:
                table_names.add(node["name"])
                
        # Traverse from Metrics to Tables
        metric_names = [m[0]["name"] if isinstance(m, list) else m.get("node", {}).get("name") for m in metrics if m]
        metric_names = [m for m in metric_names if m]
        if metric_names:
            m_table_query = """
            UNWIND $names AS name
            MATCH (m:Metric {name: name})-[:CALCULATED_FROM]->(t:Table)
            RETURN DISTINCT t.name AS table_name
            """
            m_tables = await self._query_graph(m_table_query, {"names": metric_names})
            for row in m_tables:
                name = row[0] if isinstance(row, list) else row.get("table_name")
                if name:
                    table_names.add(name)
                    
        # Traverse from Dimensions to Tables
        dim_names = [d[0]["name"] if isinstance(d, list) else d.get("node", {}).get("name") for d in dimensions if d]
        dim_names = [d for d in dim_names if d]
        if dim_names:
            d_table_query = """
            UNWIND $names AS name
            MATCH (d:Dimension {name: name})-[:BELONGS_TO_CONCEPT]->(c:Column)-[:BELONGS_TO]->(t:Table)
            RETURN DISTINCT t.name AS table_name
            """
            d_tables = await self._query_graph(d_table_query, {"names": dim_names})
            for row in d_tables:
                name = row[0] if isinstance(row, list) else row.get("table_name")
                if name:
                    table_names.add(name)
                    
                
        # For columns, find their parent tables
        if columns:
            col_names = [c[0]["name"] if isinstance(c, list) else c.get("node", {}).get("name") for c in columns if c]
            col_names = [c for c in col_names if c]
            if col_names:
                table_query = """
                UNWIND $col_names AS col_name
                MATCH (c:Column {name: col_name})-[:BELONGS_TO]->(t:Table)
                RETURN DISTINCT t.name AS table_name
                """
                parent_tables = await self._query_graph(table_query, {"col_names": col_names})
                for row in parent_tables:
                    name = row[0] if isinstance(row, list) else row.get("table_name")
                    if name:
                        table_names.add(name)
                        
        # Add explicitly referenced tables via Foreign Keys (1 level deep)
        if table_names:
            fk_query = """
            UNWIND $table_names AS t_name
            MATCH (t:Table {name: t_name})
            WHERE t.foreign_keys IS NOT NULL
            RETURN t.foreign_keys AS fks
            """
            fks_results = await self._query_graph(fk_query, {"table_names": list(table_names)})
            import json
            for row in fks_results:
                fks_str = row[0] if isinstance(row, list) else row.get("fks")
                if fks_str and fks_str != "[]":
                    try:
                        fks_list = json.loads(fks_str)
                        for fk in fks_list:
                            ref = fk.get("referred_table")
                            if ref:
                                table_names.add(ref)
                    except:
                        pass
                        
        # Extract full table schemas for relevant tables
        context_parts = []
        
        
        graph_data = {"nodes": [], "edges": []}
        node_ids = set()

        def add_node(n_id, label, name, props):
            if n_id not in node_ids:
                graph_data["nodes"].append({"id": n_id, "label": label, "name": name, "properties": props})
                node_ids.add(n_id)

        if metrics or dimensions:
            context_parts.append("### Business Logic (Semantic Layer)")
            for m in metrics:
                node = m[0] if isinstance(m, list) else m.get("node", {})
                if node:
                    name = node.get('name')
                    context_parts.append(f"- **Metric:** {name} | Formula: {node.get('formula')} | Desc: {node.get('description')}")
                    add_node(f"metric_{name}", "Metric", name, {"formula": node.get('formula')})
                    
            for d in dimensions:
                node = d[0] if isinstance(d, list) else d.get("node", {})
                if node:
                    name = node.get('name')
                    context_parts.append(f"- **Dimension:** {name} | Desc: {node.get('description')}")
                    add_node(f"dimension_{name}", "Dimension", name, {})
            context_parts.append("")

        if table_names:
            context_parts.append("### Database Schema")
            schema_query = """
            UNWIND $table_names AS t_name
            MATCH (t:Table {name: t_name})
            OPTIONAL MATCH (c:Column)-[:BELONGS_TO]->(t)
            RETURN t.name AS table_name, t.description AS table_desc, t.foreign_keys AS foreign_keys,
                   collect({name: c.name, type: c.type, desc: c.description, key: c.key_type}) AS columns
            """
            schemas = await self._query_graph(schema_query, {"table_names": list(table_names)})
            
            for row in schemas:
                if isinstance(row, dict):
                    t_name = row.get("table_name")
                    t_desc = row.get("table_desc")
                    fks = row.get("foreign_keys")
                    cols = row.get("columns", [])
                else:
                    t_name, t_desc, fks, cols = row[0], row[1], row[2], row[3]
                
                add_node(f"table_{t_name}", "Table", t_name, {"description": t_desc})
                
                # Try to link metrics/dimensions to tables if they match by name heuristically for visualization
                # Or just let them float.
                
                context_parts.append(f"**Table: {t_name}**")
                if t_desc:
                    context_parts.append(f"Description: {t_desc}")
                if fks and fks != "[]":
                    context_parts.append(f"Foreign Keys: {fks}")
                    # Simple heuristic to extract referenced tables to create edges
                    import re
                    import json
                    try:
                        fks_list = json.loads(fks)
                        for fk in fks_list:
                            ref_table = fk.get("referred_table")
                            if ref_table and ref_table in table_names:
                                graph_data["edges"].append({
                                    "source": f"table_{t_name}",
                                    "target": f"table_{ref_table}",
                                    "label": "FOREIGN_KEY"
                                })
                    except:
                        pass
                        
                context_parts.append("Columns:")
                for col in cols:
                    if col and col.get("name"):
                        context_parts.append(f"  - {col.get('name')} ({col.get('type')}): {col.get('desc')} {'[PK/FK]' if col.get('key') and col.get('key') != 'unknown' else ''}")
                context_parts.append("")
                
        # Link user question to top nodes
        graph_data["nodes"].append({"id": "question", "label": "Question", "name": question, "properties": {}})
        for n in graph_data["nodes"]:
            if n["id"] != "question":
                graph_data["edges"].append({"source": "question", "target": n["id"], "label": "SIMILAR_TO"})
                
        return "\n".join(context_parts), graph_data
