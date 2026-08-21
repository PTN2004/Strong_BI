import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.graph_db.factory import GraphDatabaseFactory
from api.config import Config

async def fix():
    db = await GraphDatabaseFactory.get_instance()
    all_graphs = await db.list_graph()
    target_graph = next((g for g in all_graphs if "dms" in g.lower()), None)
    db.select_graph(target_graph)
    
    # Drop indices
    for label in ["Table", "Metric", "Dimension", "Column"]:
        try:
            await db.query(f"DROP INDEX {label}_embedding_index IF EXISTS")
            print(f"Dropped {label} index")
        except Exception as e:
            print(e)
            pass

    # Create new indices
    vec_len = Config.EMBEDDING_MODEL.get_vector_size()
    print(f"New vector size: {vec_len}")
    for label in ["Table", "Metric", "Dimension"]:
        try:
            await db.create_vector_index(node_label=label, property_name="embedding", dimension=vec_len)
            print(f"Created {label} index with dim {vec_len}")
        except Exception as e:
            print(e)
            pass

    # Re-embed Tables
    try:
        tables = await db.query("MATCH (t:Table) RETURN t.name as name, t.description as desc")
        if tables and hasattr(tables, 'result_set'):
            for row in tables.result_set:
                desc = row.get("desc") or row.get("name") or " "
                if not str(desc).strip(): desc = " "
                emb_result = Config.EMBEDDING_MODEL.embed(desc)
                if emb_result:
                    emb = emb_result[0]
                    await db.query("MATCH (t:Table {name: $name}) SET t.embedding = $emb", {"name": row.get("name"), "emb": emb})
                    print(f"Re-embedded Table {row.get('name')}")
    except Exception as e:
        print(f"Error tables: {e}")

    # Re-embed Metrics
    try:
        metrics = await db.query("MATCH (m:Metric) RETURN m.name as name, m.description as desc")
        if metrics and hasattr(metrics, 'result_set'):
            for row in metrics.result_set:
                desc = row.get("desc") or row.get("name") or " "
                if not str(desc).strip(): desc = " "
                emb_result = Config.EMBEDDING_MODEL.embed(desc)
                if emb_result:
                    emb = emb_result[0]
                    await db.query("MATCH (m:Metric {name: $name}) SET m.embedding = $emb", {"name": row.get("name"), "emb": emb})
                    print(f"Re-embedded Metric {row.get('name')}")
    except Exception as e:
        print(f"Error metrics: {e}")

    # Re-embed Dimensions
    try:
        dims = await db.query("MATCH (d:Dimension) RETURN d.name as name, d.description as desc")
        if dims and hasattr(dims, 'result_set'):
            for row in dims.result_set:
                desc = row.get("desc") or row.get("name") or " "
                if not str(desc).strip(): desc = " "
                emb_result = Config.EMBEDDING_MODEL.embed(desc)
                if emb_result:
                    emb = emb_result[0]
                    await db.query("MATCH (d:Dimension {name: $name}) SET d.embedding = $emb", {"name": row.get("name"), "emb": emb})
                    print(f"Re-embedded Dimension {row.get('name')}")
    except Exception as e:
        print(f"Error dims: {e}")

if __name__ == "__main__":
    asyncio.run(fix())
