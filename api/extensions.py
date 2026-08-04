"""Extensions module for global state management."""

import logging
from typing import Optional

from api.graph_db import GraphDatabase, GraphDatabaseFactory

logger = logging.getLogger(__name__)

_db: Optional[GraphDatabase] = None


async def get_default_db() -> GraphDatabase:
    global _db
    
    if _db is not None and _db.is_connected():
        return _db

    try:
        _db = GraphDatabaseFactory.create()
        
        await _db.connect()
        logger.info(f"Global Connection established for: {_db.db_type.upper()}")
        
    except Exception as e:
        logger.error(f"Failed to initialize Graph Database: {e}")
        raise ConnectionError(f"Failed to initialize Graph Database: {e}") from e

    return _db


async def close_default_db() -> None:
    global _db
    if _db:
        await _db.disconnect()
        logger.info(f"Closed global connection for: {_db.db_type.upper()}")
        _db = None