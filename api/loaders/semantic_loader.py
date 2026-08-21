import logging
from typing import Dict, Any
from api.graph_db import GraphDatabaseFactory
from api.config import Config

logger = logging.getLogger(__name__)

async def get_semantic_layer(graph_id: str, db=None) -> Dict[str, Any]:
    """
    Retrieve semantic layer (Metrics and Dimensions) from Graph Database.
    """
    should_disconnect = False
    if db is None:
        db = GraphDatabaseFactory.create()
        await db.connect()
        should_disconnect = True
        
    graph = db
    
    try:
        graph.select_graph(graph_id)
        
        result_metrics = await graph.query(
            """
            MATCH (m:Metric)
            OPTIONAL MATCH (m)-[:CALCULATED_FROM]->(t:Table)
            RETURN m.name as name, m.description as description, m.formula as formula, t.name as table
            """,
            {}
        )
        
        metrics = []
        for r in result_metrics.result_set:
            metrics.append({
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "formula": r.get("formula", ""),
                "table": r.get("table", "") if r.get("table") else ""
            })
            
        result_dimensions = await graph.query(
            """
            MATCH (d:Dimension)
            OPTIONAL MATCH (d)-[:BELONGS_TO_CONCEPT]->(c:Column)-[:BELONGS_TO]->(t:Table)
            RETURN d.name as name, d.description as description, c.name as column, t.name as table
            """,
            {}
        )
        
        dimensions = []
        for r in result_dimensions.result_set:
            dimensions.append({
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "column": r.get("column", "") if r.get("column") else "",
                "table": r.get("table", "") if r.get("table") else ""
            })
            
        return {
            "metrics": metrics,
            "dimensions": dimensions
        }
    finally:
        if should_disconnect:
            await graph.disconnect()

async def delete_semantic_node(graph_id: str, node_type: str, name: str, db=None) -> None:
    """
    Delete a specific semantic node (Metric or Dimension).
    """
    should_disconnect = False
    if db is None:
        db = GraphDatabaseFactory.create()
        await db.connect()
        should_disconnect = True
        
    graph = db
    
    try:
        graph.select_graph(graph_id)
        label = "Metric" if node_type.lower() == "metric" else "Dimension"
        
        await graph.query(
            f"""
            MATCH (n:{label} {{name: $name}})
            DETACH DELETE n
            """,
            {"name": name}
        )
    finally:
        if should_disconnect:
            await graph.disconnect()

async def load_semantic_layer(
    graph_id: str,
    semantic_data: Dict[str, Any],
    db=None,
) -> None:
    """
    Load semantic business logic (Metrics, Dimensions) into the Graph Database.
    semantic_data format:
    {
        "metrics": [
            {
                "name": "revenue",
                "description": "Total revenue",
                "formula": "SUM(amount) - SUM(tax)",
                "table": "orders"
            }
        ],
        "dimensions": [
            {
                "name": "user_segment",
                "description": "Age segmentation",
                "table": "users",
                "column": "age"
            }
        ]
    }
    """
    should_disconnect = False
    if db is None:
        db = GraphDatabaseFactory.create()
        await db.connect()
        should_disconnect = True
        
    graph = db
    embedding_model = Config.EMBEDDING_MODEL
    vec_len = embedding_model.get_vector_size()
    
    try:
        graph.select_graph(graph_id)
        
        # Create Vector Indices for Semantic Nodes
        try:
            await graph.create_vector_index(
                node_label="Metric",
                property_name="embedding",
                dimension=vec_len
            )
            await graph.create_vector_index(
                node_label="Dimension",
                property_name="embedding",
                dimension=vec_len
            )
        except Exception as e:
            logger.warning(f"Error creating vector indices for semantic nodes: {str(e)}")

        metrics = semantic_data.get("metrics", [])
        for metric in metrics:
            metric_name = metric["name"]
            description = metric.get("description", "")
            formula = metric.get("formula", "")
            target_table = metric.get("table", "")
            
            import asyncio
            embedding_result = await asyncio.to_thread(embedding_model.embed, description)
            
            await graph.query(
                f"""
                MERGE (m:Metric {{name: $metric_name}})
                SET m.description = $description,
                    m.formula = $formula,
                    m.embedding = {graph.format_vector("embedding")}
                WITH m
                OPTIONAL MATCH (t:Table {{name: $table_name}})
                FOREACH (ignoreMe in CASE WHEN t IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (m)-[:CALCULATED_FROM]->(t)
                )
                """,
                {
                    "table_name": target_table,
                    "metric_name": metric_name,
                    "description": description,
                    "formula": formula,
                    "embedding": embedding_result[0]
                }
            )
            logger.info(f"Loaded Metric: {metric_name}")
            
        dimensions = semantic_data.get("dimensions", [])
        for dim in dimensions:
            dim_name = dim["name"]
            description = dim.get("description", "")
            target_table = dim.get("table", "")
            target_col = dim.get("column", "")
            
            import asyncio
            embedding_result = await asyncio.to_thread(embedding_model.embed, description)
            
            await graph.query(
                f"""
                MERGE (d:Dimension {{name: $dim_name}})
                SET d.description = $description,
                    d.embedding = {graph.format_vector("embedding")}
                WITH d
                OPTIONAL MATCH (c:Column {{name: $col_name}})-[:BELONGS_TO]->(t:Table {{name: $table_name}})
                FOREACH (ignoreMe in CASE WHEN c IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (d)-[:BELONGS_TO_CONCEPT]->(c)
                )
                """,
                {
                    "table_name": target_table,
                    "col_name": target_col,
                    "dim_name": dim_name,
                    "description": description,
                    "embedding": embedding_result[0]
                }
            )
            logger.info(f"Loaded Dimension: {dim_name}")
            
    finally:
        if should_disconnect:
            await graph.disconnect()
