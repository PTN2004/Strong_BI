import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.graph_db.factory import GraphDatabaseFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("load_wrenai_relationships")


def parse_condition(condition: str):
    """
    Parses condition string like: "sale_order.customer_id = customer.customer_id"
    or "area.area_id::text = customer.area_id"
    Returns (source_table, source_col, target_table, target_col) or None
    """
    clean_cond = re.sub(r"::[a-zA-Z0-9_]+", "", condition)
    match = re.match(r"^\s*([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*$", clean_cond)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3), match.group(4)


async def auto_infer_relationships(db, graph_name: str):
    """
    Queries Neo4j/GraphDB nodes to auto-infer missing relationships based on naming conventions (*_id).
    """
    logger.info(f"Running Auto-Inference for graph: '{graph_name}'...")
    db.select_graph(graph_name)

    query = """
    MATCH (c:Column)-[:BELONGS_TO]->(t:Table)
    RETURN t.name AS table_name, c.name AS col_name
    """
    try:
        res = await db.query(query)
        rows = res.result_set if hasattr(res, 'result_set') else []
    except Exception as e:
        logger.error(f"Failed to query schema for auto-inference: {e}")
        return 0

    table_cols = {}
    for row in rows:
        t_name = row[0] if isinstance(row, (list, tuple)) else row.get("table_name")
        c_name = row[1] if isinstance(row, (list, tuple)) else row.get("col_name")
        if t_name and c_name:
            table_cols.setdefault(t_name, set()).add(c_name)

    inferred_rels = []
    for src_table, cols in table_cols.items():
        for col in cols:
            if col.endswith("_id") and col != "id":
                ref_base = col[:-3]
                candidates = [ref_base, ref_base + "s", ref_base[:-1] if ref_base.endswith("s") else ref_base]
                for tgt in candidates:
                    if tgt in table_cols and tgt != src_table:
                        tgt_cols = table_cols[tgt]
                        if col in tgt_cols:
                            tgt_col = col
                        elif f"{ref_base}_id" in tgt_cols:
                            tgt_col = f"{ref_base}_id"
                        elif "id" in tgt_cols:
                            tgt_col = "id"
                        else:
                            continue
                        inferred_rels.append((src_table, col, tgt, tgt_col, f"auto_{src_table}_{col}__{tgt}"))
                        break

    logger.info(f"Auto-inferred {len(inferred_rels)} candidate relationships for '{graph_name}'.")

    added_count = 0
    for src_table, src_col, tgt_table, tgt_col, rel_name in inferred_rels:
        cypher = """
        MATCH (src:Column {name: $source_col})-[:BELONGS_TO]->(source:Table {name: $source_table})
        MATCH (tgt:Column {name: $target_col})-[:BELONGS_TO]->(target:Table {name: $target_table})
        MERGE (src)-[r:REFERENCES {rel_name: $rel_name}]->(tgt)
        SET r.join_type = 'AUTO_INFERRED'
        RETURN count(r) as count
        """
        try:
            await db.query(
                cypher,
                {
                    "source_table": src_table,
                    "source_col": src_col,
                    "target_table": tgt_table,
                    "target_col": tgt_col,
                    "rel_name": rel_name,
                }
            )
            added_count += 1
        except Exception as e:
            logger.error(f"Failed to create auto-inferred rel {rel_name}: {e}")

    return added_count


async def main():
    parser = argparse.ArgumentParser(description="Import relationships from WrenAI seed JSON and auto-infer missing ones in StrongBI Graph Database.")
    parser.add_argument(
        "--file",
        type=str,
        default="../dms/requirements/wrenai_seed.json",
        help="Path to wrenai_seed.json file"
    )
    parser.add_argument(
        "--graph-id",
        type=str,
        default=None,
        help="Target Graph ID in Graph DB"
    )
    parser.add_argument(
        "--no-infer",
        action="store_true",
        help="Disable auto-inference of missing relationships"
    )

    args = parser.parse_args()

    relationships = []
    json_path = Path(args.file).resolve()
    if json_path.exists():
        logger.info(f"Loading seed file from {json_path}...")
        with open(json_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)
        relationships = seed_data.get("mdl", {}).get("relationships", [])
        logger.info(f"Found {len(relationships)} explicit relationship definitions in JSON.")
    else:
        logger.warning(f"File not found: {json_path}. Proceeding with auto-inference only.")

    db = await GraphDatabaseFactory.get_instance()
    
    all_graphs = await db.list_graph()
    logger.info(f"Available graphs in DB: {all_graphs}")

    target_graphs = []
    if args.graph_id:
        target_graphs = [args.graph_id]
    else:
        target_graphs = [g for g in all_graphs if "dms" in g.lower()]
        if not target_graphs and all_graphs:
            target_graphs = all_graphs

    if not target_graphs:
        logger.error("No target graph found in database! Please load schema into StrongBI first via UI or API.")
        sys.exit(1)

    for graph_name in target_graphs:
        logger.info(f"Applying explicit relationships to graph: '{graph_name}'...")
        db.select_graph(graph_name)

        success_count = 0
        skip_count = 0

        for rel in relationships:
            rel_name = rel.get("name", "")
            condition = rel.get("condition", "")
            join_type = rel.get("joinType", "MANY_TO_ONE")

            parsed = parse_condition(condition)
            if not parsed:
                logger.warning(f"Could not parse condition '{condition}' for relationship '{rel_name}'")
                skip_count += 1
                continue

            source_table, source_col, target_table, target_col = parsed

            cypher = """
            MATCH (src:Column {name: $source_col})-[:BELONGS_TO]->(source:Table {name: $source_table})
            MATCH (tgt:Column {name: $target_col})-[:BELONGS_TO]->(target:Table {name: $target_table})
            MERGE (src)-[r:REFERENCES {rel_name: $rel_name}]->(tgt)
            SET r.join_type = $join_type
            RETURN count(r) as count
            """

            try:
                await db.query(
                    cypher,
                    {
                        "source_table": source_table,
                        "source_col": source_col,
                        "target_table": target_table,
                        "target_col": target_col,
                        "rel_name": rel_name,
                        "join_type": join_type,
                    }
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to create relationship {rel_name}: {e}")
                skip_count += 1

        logger.info(f"Explicit relationships done for '{graph_name}': {success_count} processed.")

        if not args.no_infer:
            inferred_count = await auto_infer_relationships(db, graph_name)
            logger.info(f"Auto-inference done for '{graph_name}': {inferred_count} added.")

if __name__ == "__main__":
    asyncio.run(main())
