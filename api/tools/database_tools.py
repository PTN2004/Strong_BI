import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

async def get_table_schema(db, table_names: List[str]) -> str:
    """
    Get detailed schema (columns, types, descriptions, foreign keys) for specific tables.
    """
    if not table_names:
        return "Please provide at least one table name."
        
    query = """
    MATCH (table:Table)-[:BELONGS_TO]-(columns)
    WHERE table.name IN $table_names
    RETURN table.name AS name, table.description AS description, table.foreign_keys AS foreign_keys,
           collect({
               columnName: columns.name, 
               description: columns.description, 
               dataType: columns.type, 
               keyType: coalesce(columns.key_type, ''), 
               nullable: columns.nullable
           }) AS columns
    """
    try:
        result = await db.query(query, {"table_names": table_names})
        formatted = []
        for row in result.result_set:
            if isinstance(row, dict):
                formatted.append(f"Table: {row.get('name')}\nDescription: {row.get('description')}\nForeign Keys: {row.get('foreign_keys')}\nColumns: {json.dumps(row.get('columns'), ensure_ascii=False)}")
            else:
                formatted.append(str(row))
        return "\n\n".join(formatted) if formatted else f"No tables found matching: {table_names}"
    except Exception as e:
        logger.error(f"Error in get_table_schema: {e}")
        return f"Error retrieving schema: {e}"


async def search_all_tables(db) -> str:
    """
    Returns a list of ALL tables in the database with their descriptions.
    Use this to explore what tables are available.
    """
    query = """
    MATCH (table:Table)
    RETURN table.name AS name, table.description AS description
    """
    try:
        result = await db.query(query)
        formatted = []
        for row in result.result_set:
            if isinstance(row, dict):
                formatted.append(f"- {row.get('name')}: {row.get('description')}")
        return "Available Tables:\n" + "\n".join(formatted)
    except Exception as e:
        logger.error(f"Error in search_all_tables: {e}")
        return f"Error retrieving tables: {e}"


def execute_test_sql(loader_class, db_url: str, sql: str) -> str:
    """
    Execute a SELECT SQL query against the real database to test it.
    Limit your queries to 5 rows (e.g. LIMIT 5) to avoid huge outputs.
    """
    if "update" in sql.lower() or "delete" in sql.lower() or "drop" in sql.lower() or "insert" in sql.lower():
        return "Error: Only SELECT queries are allowed for testing."
        
    try:
        results = loader_class.execute_sql_query(sql, db_url)
        return json.dumps(results[:5], ensure_ascii=False, indent=2)
    except Exception as e:
        return f"SQL Error:\n{str(e)}"

# Define the Tool schemas for LiteLLM / OpenAI API
DATABASE_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_all_tables",
            "description": "Get a list of all available tables in the database along with their descriptions. Call this first to understand what data exists.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_table_schema",
            "description": "Get detailed schema information (columns, types, foreign keys) for a specific list of tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of table names to get schema for (e.g. ['users', 'orders'])"
                    }
                },
                "required": ["table_names"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_test_sql",
            "description": "Run a SELECT query on the actual database to test if it works and view sample data. Always use LIMIT 5.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute."
                    }
                },
                "required": ["sql"]
            }
        }
    }
]
