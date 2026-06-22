from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from api.graph_db import GraphDatabase, GraphDatabaseFactory
    
def resolver_db(db: Optional[GraphDatabase] = None) -> GraphDatabase:
    if db is not None:
        return db
    
    return GraphDatabaseFactory.create()