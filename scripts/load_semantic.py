import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.loaders.semantic_loader import load_semantic_layer
from api.graph_db.factory import GraphDatabaseFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("load_semantic")

async def main():
    json_path = Path("../dms/requirements/strongbi_semantic.json").resolve()
    if not json_path.exists():
        logger.error(f"File not found: {json_path}")
        sys.exit(1)

    logger.info(f"Loading Semantic Data from {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        semantic_data = json.load(f)

    db = await GraphDatabaseFactory.get_instance()
    
    # Get all graph names
    all_graphs = await db.list_graph()
    
    # Target DMS graph
    target_graph = next((g for g in all_graphs if "dms" in g.lower()), None)
    
    if not target_graph:
        logger.error("No graph found containing 'dms' in Neo4j. Please load database schema first.")
        sys.exit(1)

    logger.info(f"Injecting Semantic Embeddings into Graph Database: {target_graph}")
    try:
        await load_semantic_layer(graph_id=target_graph, semantic_data=semantic_data, db=db)
        logger.info("Semantic Layer injection completed successfully!")
    except Exception as e:
        logger.error(f"Failed to inject semantic layer: {e}")

if __name__ == "__main__":
    asyncio.run(main())
