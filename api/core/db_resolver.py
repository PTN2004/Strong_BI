from typing import Optional

from api.graph_db import GraphDatabase, GraphDatabaseFactory
    
def resolver_db(db: Optional[GraphDatabase] = None) -> GraphDatabase:
    if db is not None:
        return db
    
    if GraphDatabaseFactory._instance is not None:
        return GraphDatabaseFactory._instance
        
    return GraphDatabaseFactory.create()