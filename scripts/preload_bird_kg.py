#!/usr/bin/env python
import os
import sys
import asyncio
import argparse
import logging
from typing import Set

# Add the project root to sys.path so we can import from api and benchmark
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from api.core.schema_loader import load_database_sync
from api.graph_db import GraphDatabaseFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BIRD_Preloader")

async def preload_databases(db_dir: str):
    logger.info(f"Looking for SQLite databases in: {db_dir}")
    
    if not os.path.exists(db_dir):
        logger.error(f"Directory {db_dir} does not exist.")
        return

    # Check existing graphs
    existing_graphs: Set[str] = set()
    db_factory = None
    try:
        db_factory = GraphDatabaseFactory.create()
        await db_factory.connect()
        existing_graphs = set(await db_factory.list_graph())
        logger.info(f"Found {len(existing_graphs)} existing graphs in GraphDB.")
    except Exception as e:
        logger.warning(f"Could not connect to GraphDB to fetch existing graphs: {e}")
    finally:
        if db_factory:
            try:
                await db_factory.disconnect()
            except Exception:
                pass

    user_id = "bird_eval"
    
    # Iterate over subdirectories
    count = 0
    success_count = 0
    items = sorted(os.listdir(db_dir))
    for item in items:
        item_path = os.path.join(db_dir, item)
        if os.path.isdir(item_path):
            db_id = item
            db_file = os.path.join(item_path, f"{db_id}.sqlite")
            if os.path.exists(db_file):
                count += 1
                graph_name = f"{user_id}_{db_id}"
                if graph_name in existing_graphs:
                    logger.info(f"[{count}] DB '{db_id}' already exists in GraphDB. Skipping.")
                    success_count += 1
                    continue
                
                sqlite_url = f"sqlite:///{os.path.abspath(db_file)}"
                logger.info(f"[{count}] Loading DB '{db_id}' to GraphDB (Graph ID: {graph_name})...")
                
                try:
                    result = await load_database_sync(sqlite_url, user_id)
                    if result and result.success:
                        logger.info(f"  -> Successfully loaded {db_id}")
                        success_count += 1
                    else:
                        logger.error(f"  -> Failed to load {db_id}: {result.message if result else 'Unknown error'}")
                except Exception as e:
                    logger.exception(f"  -> Exception while loading {db_id}: {e}")

    logger.info(f"Preloading complete! Successfully loaded/verified {success_count}/{count} databases.")

def main():
    parser = argparse.ArgumentParser(description="Preload BIRD databases into GraphDB")
    parser.add_argument("--db-dir", type=str, required=True, help="Directory containing BIRD databases folder (db_id/db_id.sqlite)")
    args = parser.parse_args()
    
    asyncio.run(preload_databases(args.db_dir))

if __name__ == "__main__":
    main()
