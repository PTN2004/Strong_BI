import json
import tqdm
import asyncio

from api.graph_db import GraphDatabaseFactory, GraphDatabase
from api.config import Config
from api.utils import generate_db_description, create_combined_description


async def load_to_graph(  
    graph_id: str,
    entities: dict,
    relationships: dict,
    batch_size: int = 100,
    db_name: str = "TBD",
    db_url: str = "",
    db=None,
) -> None:
    
    should_disconnect = False
    if db is None:
        db = GraphDatabaseFactory.create()
        await db.connect()
        should_disconnect = True
        
    graph = db
    embedding_model = Config.EMBEDDING_MODEL
    vec_len = embedding_model.get_vector_size()

    if Config.USE_LLM_FOR_SCHEMA_DESC:
        await asyncio.to_thread(create_combined_description, entities)
    try:
        graph.select_graph(graph_id)
        try:
            await graph.create_vector_index(
                node_label="Table",
                property_name="embedding",
                dimension=vec_len
            )
            
            await graph.create_vector_index(
                node_label="Column",
                property_name="embedding",
                dimension=vec_len
            )
            await graph.create_index(node_label="Table", property_name="name")
        except Exception as e:  
            print(f"Error creating vector indices: {str(e)}")

        if Config.USE_LLM_FOR_SCHEMA_DESC:
            db_des = await asyncio.to_thread(generate_db_description, db_name=db_name, table_names=list(entities.keys()))
        else:
            db_des = f"Database containing {len(entities.keys())} tables."
        await graph.query(
            """
            MERGE (d:Database {name: $db_name})
            SET d.description = $description, d.url = $url
            """,
            {"db_name": db_name, "description": db_des, "url": db_url},
        )

        for table_name, table_info in tqdm.tqdm(entities.items(), desc="Creating Graph Table Nodes"):
            table_desc = table_info["description"]
            embedding_result = await asyncio.to_thread(embedding_model.embed, table_desc)
            fk = json.dumps(table_info.get("foreign_keys", []))

            await graph.query(
                f"""
                MERGE (t:Table {{name: $table_name}})
                SET t.description = $description,
                    t.embedding = {graph.format_vector("embedding")},
                    t.foreign_keys = $foreign_keys
                """,
                {
                    "table_name": table_name,
                    "description": table_desc,
                    "embedding": embedding_result[0],
                    "foreign_keys": fk,
                },
            )

            batch_flag = True
            col_descriptions = table_info.get("col_descriptions")
            if col_descriptions is None:
                batch_flag = False
            else:
                try:
                    embed_columns = []
                    for batch in tqdm.tqdm(
                        [
                            col_descriptions[i : i + batch_size]
                            for i in range(0, len(col_descriptions), batch_size)
                        ],
                        desc=f"Creating embeddings for {table_name} columns",
                    ):

                        embedding_result = await asyncio.to_thread(embedding_model.embed, batch)
                        embed_columns.extend(embedding_result)
                except Exception as e:  
                    print(f"Error creating embeddings: {str(e)}")
                    batch_flag = False

            for idx, (col_name, col_info) in tqdm.tqdm(
                enumerate(table_info["columns"].items()),
                desc=f"Creating Graph Columns for {table_name}",
                total=len(table_info["columns"]),
            ):
                if not batch_flag:
                    embed_columns = []
                    embedding_result = await asyncio.to_thread(embedding_model.embed, col_info["description"])
                    embed_columns.extend(embedding_result)
                    idx = 0

                final_description = col_info["description"]
                sample_values = col_info.get("sample_values", [])
                if sample_values:
                    sample_values_str = f"(Sample values: {', '.join(f'({v})' for v in sample_values)})"
                    final_description = f"{final_description} {sample_values_str}"

                await graph.query(
                    f"""
                    MATCH (t:Table {{name: $table_name}})
                    MERGE (c:Column {{name: $col_name}})-[:BELONGS_TO]->(t)
                    SET c.type = $type,
                        c.nullable = $nullable,
                        c.key_type = $key,
                        c.description = $description,
                        c.embedding = {graph.format_vector("embedding")}
                    """,
                    {
                        "table_name": table_name,
                        "col_name": col_name,
                        "type": col_info.get("type", "unknown"),
                        "nullable": col_info.get("null", "unknown"),
                        "key": col_info.get("key", "unknown"),
                        "description": final_description,
                        "embedding": embed_columns[idx],
                    },
                )

        for rel_name, table_info in tqdm.tqdm(
            relationships.items(), desc="Creating Graph Table Relationships"
        ):
            for rel in table_info:
                source_table = rel["from"]
                source_field = rel["source_column"]
                target_table = rel["to"]
                target_field = rel["target_column"]
                note = rel.get("note", "")

                # Create relationship if both tables and columns exist
                try:
                    await graph.query(
                        """
                        MATCH (src:Column {name: $source_col})
                            -[:BELONGS_TO]->(source:Table {name: $source_table})
                        MATCH (tgt:Column {name: $target_col})
                            -[:BELONGS_TO]->(target:Table {name: $target_table})
                        CREATE (src)-[:REFERENCES {
                            rel_name: $rel_name,
                            note: $note
                        }]->(tgt)
                        """,
                        {
                            "source_col": source_field,
                            "target_col": target_field,
                            "source_table": source_table,
                            "target_table": target_table,
                            "rel_name": rel_name,
                            "note": note,
                        },
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    print(f"Warning: Could not create relationship: {str(e)}")
                    continue
    finally:
        if should_disconnect:
            await graph.disconnect()
        
    
