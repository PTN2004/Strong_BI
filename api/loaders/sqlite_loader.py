"""SQLite loader for loading database schemas into FalkorDB graphs."""

import re
import sqlite3
import datetime
import logging
from typing import AsyncGenerator, Dict, Any, List, Tuple
from urllib.parse import urlparse

import tqdm

from api.loaders.base_loader import BaseLoader  # pylint: disable=import-error
from api.loaders.graph_loader import load_to_graph  # pylint: disable=import-error

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class SQLiteQueryError(Exception):
    """Exception raised when SQLite query execution fails."""


class SQLiteConnectionError(Exception):
    """Exception raised when SQLite connection fails."""


class SQLiteLoader(BaseLoader):
    """
    Loader for SQLite databases that connects and extracts schema information.
    """

    # DDL operations that modify database schema
    SCHEMA_MODIFYING_OPERATIONS = {
        'CREATE', 'ALTER', 'DROP', 'RENAME', 'TRUNCATE'
    }

    # More specific patterns for schema-affecting operations
    SCHEMA_PATTERNS = [
        r'^\s*CREATE\s+TABLE',
        r'^\s*CREATE\s+INDEX',
        r'^\s*CREATE\s+UNIQUE\s+INDEX',
        r'^\s*ALTER\s+TABLE',
        r'^\s*DROP\s+TABLE',
        r'^\s*DROP\s+INDEX',
        r'^\s*RENAME\s+TABLE',
        r'^\s*TRUNCATE\s+TABLE',
        r'^\s*CREATE\s+VIEW',
        r'^\s*DROP\s+VIEW',
    ]

    @staticmethod
    def _execute_sample_query(
        cursor: Any, table_name: str, col_name: str, sample_size: int = 3
    ) -> List[Any]:
        try:
            query = f"""
                SELECT DISTINCT "{col_name}"
                FROM "{table_name}"
                WHERE "{col_name}" IS NOT NULL
                ORDER BY RANDOM()
                LIMIT ?;
            """
            cursor.execute(query, (sample_size,))
            sample_results = cursor.fetchall()
            return [row[0] for row in sample_results if row[0] is not None]
        except sqlite3.Error as e:
            logging.warning(f"Failed to get sample values for {table_name}.{col_name}: {e}")
            return []

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        if isinstance(value, datetime.time):
            return value.isoformat()
        if value is None:
            return None
        return value

    @staticmethod
    def parse_sqlite_path(connection_url: str) -> str:
        try:
            if connection_url.startswith('sqlite://'):
                path = connection_url[9:]
                
                if path.startswith('/'):
                    return path
                else:
                    return path
            
            elif connection_url.startswith('file:'):
                return connection_url[5:]
            
            else:
                return connection_url

        except Exception:  
            return connection_url

    @staticmethod
    async def load(  
        prefix: str,
        connection_url: str,
        db=None,
    ) -> AsyncGenerator[tuple[bool, str], None]:
        conn = None
        cursor = None
        try:
            db_path = SQLiteLoader.parse_sqlite_path(connection_url)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA foreign_keys = ON;")

            db_name = db_path.split('/')[-1].replace('.db', '')

            yield True, "Extracting table information..."
            entities = SQLiteLoader.extract_tables_info(cursor)

            yield True, "Extracting relationship information..."
            relationships = SQLiteLoader.extract_relationships(cursor)

            cursor.close()
            cursor = None
            conn.close()
            conn = None

            yield True, "Loading data into graph..."
            # Load data into graph
            await load_to_graph(
                f"{prefix}_{db_name}", 
                entities, 
                relationships,
                db_name=db_name, 
                db_url=connection_url, 
                db=db
            )

            yield True, (f"SQLite schema loaded successfully. "
                         f"Found {len(entities)} tables.")

        except sqlite3.DatabaseError as e:
            logging.error("SQLite database error: %s", e)
            yield False, "Failed to access SQLite database"
        except sqlite3.OperationalError as e:
            logging.error("SQLite operational error: %s", e)
            yield False, f"SQLite operational error: {str(e)}"
        except FileNotFoundError as e:
            logging.error("SQLite database file not found: %s", e)
            yield False, f"SQLite database file not found: {db_path}"
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("Error loading SQLite schema: %s", e)
            yield False, "Failed to load SQLite database schema"
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()

    @staticmethod
    def extract_tables_info(cursor: Any) -> Dict[str, Any]:
        entities = {}

        # Get all tables in the database (excluding system tables)
        cursor.execute("""
            SELECT name, sql
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """)

        tables = cursor.fetchall()

        for table_name, create_sql in tqdm.tqdm(tables, desc="Extracting table information"):
            table_name = table_name.strip()

            # Get column information for this table
            columns_info = SQLiteLoader.extract_columns_info(cursor, table_name)

            # Get foreign keys for this table
            foreign_keys = SQLiteLoader.extract_foreign_keys(cursor, table_name)

            # Generate table description from CREATE TABLE statement
            table_description = create_sql if create_sql else f"Table: {table_name}"
            # Truncate very long descriptions
            if len(table_description) > 500:
                table_description = table_description[:500] + "..."

            # Get column descriptions for batch embedding
            col_descriptions = [col_info['description'] for col_info in columns_info.values()]

            entities[table_name] = {
                'description': table_description,
                'columns': columns_info,
                'foreign_keys': foreign_keys,
                'col_descriptions': col_descriptions
            }

        return entities

    @staticmethod
    def extract_columns_info(cursor: Any, table_name: str) -> Dict[str, Any]:
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = cursor.fetchall()
        columns_info = {}

        # Get foreign key info from PRAGMA
        cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
        foreign_keys_raw = cursor.fetchall()
        fk_columns = {fk[3]: fk[2] for fk in foreign_keys_raw}  # Map source_col -> table

        for cid, col_name, data_type, not_null, default_val, is_pk, *rest in columns:
            col_name = col_name.strip()

            # Determine key type
            key_type = 'NONE'
            if is_pk:
                key_type = 'PRIMARY KEY'
            elif col_name in fk_columns:
                key_type = 'FOREIGN KEY'

            # Generate column description
            description_parts = [f"Column {col_name} of type {data_type}"]

            if key_type != 'NONE':
                description_parts.append(f"({key_type})")

            if not_null:
                description_parts.append("(NOT NULL)")

            if default_val:
                description_parts.append(f"(Default: {default_val})")

            # Extract sample values for the column
            sample_values = SQLiteLoader.extract_sample_values_for_column(
                cursor, table_name, col_name
            )

            columns_info[col_name] = {
                'type': data_type,
                'null': 'NO' if not_null else 'YES',
                'key': key_type,
                'description': ' '.join(description_parts),
                'default': default_val,
                'sample_values': sample_values
            }

        return columns_info

    @staticmethod
    def extract_foreign_keys(cursor: Any, table_name: str) -> List[Dict[str, str]]:
        cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
        foreign_keys_raw = cursor.fetchall()

        foreign_keys = []
        for id_val, seq, table, from_col, to_col, on_delete, on_update, *rest in foreign_keys_raw:
            foreign_keys.append({
                'constraint_name': f"fk_{table_name}_{from_col}_{table}_{to_col}",
                'column': from_col.strip() if from_col else "",
                'referenced_table': table.strip() if table else "",
                'referenced_column': to_col.strip() if to_col else ""
            })

        return foreign_keys

    @staticmethod
    def extract_relationships(cursor: Any) -> Dict[str, List[Dict[str, str]]]:
        relationships = {}

        # Get all tables
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
        """)

        tables = cursor.fetchall()

        for (table_name, *rest) in tables:
            cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
            foreign_keys_raw = cursor.fetchall()

            for id_val, seq, ref_table, from_col, to_col, on_delete, on_update, *rest in foreign_keys_raw:
                constraint_name = f"fk_{table_name}_{from_col}_{ref_table}_{to_col}"

                if constraint_name not in relationships:
                    relationships[constraint_name] = []

                relationships[constraint_name].append({
                    'from': table_name.strip() if table_name else "",
                    'to': ref_table.strip() if ref_table else "",
                    'source_column': from_col.strip() if from_col else "",
                    'target_column': to_col.strip() if to_col else "",
                    'note': f'Foreign key constraint: {constraint_name}'
                })

        return relationships

    @staticmethod
    def is_schema_modifying_query(sql_query: str) -> Tuple[bool, str]:
        if not sql_query or not sql_query.strip():
            return False, ""

        normalized_query = sql_query.strip().upper()

        first_word = normalized_query.split()[0] if normalized_query.split() else ""
        if first_word in SQLiteLoader.SCHEMA_MODIFYING_OPERATIONS:
            for pattern in SQLiteLoader.SCHEMA_PATTERNS:
                if re.match(pattern, normalized_query, re.IGNORECASE):
                    return True, first_word

            return True, first_word

        return False, ""

    @staticmethod
    async def refresh_graph_schema(graph_id: str, db_url: str) -> Tuple[bool, str]:
        
        try:
            logging.info("Schema modification detected. Refreshing graph schema.")

            from api.graph_db import GraphDatabaseFactory  
            graph = GraphDatabaseFactory.create()
            await graph.connect()
            try:
                await graph.clear_graph()

                parts = graph_id.split('_')
                if len(parts) >= 2:
                    prefix = '_'.join(parts[:-1])
                else:
                    prefix = graph_id

                async for success, message in SQLiteLoader.load(prefix, db_url, db=graph):
                    if not success:
                        logging.error("Schema refresh failed: %s", message)
                        return False, message

                logging.info("Graph schema refreshed successfully.")
                return True, "Graph schema refreshed successfully"
            finally:
                await graph.disconnect()

        except Exception as e:  
            logging.error("Error refreshing graph schema: %s", str(e))
            return False, f"Error refreshing graph schema: {str(e)}"

    @staticmethod
    def execute_sql_query(sql_query: str, db_url: str) -> List[Dict[str, Any]]:
    
        try:
            # Parse file path from connection URL
            db_path = SQLiteLoader.parse_sqlite_path(db_url)

            # Connect to SQLite database
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()

            # Execute the SQL query
            cursor.execute(sql_query)

            # Check if the query returns results (SELECT queries)
            if cursor.description is not None:
                # This is a SELECT query or similar that returns rows
                columns = [desc[0] for desc in cursor.description]
                results = cursor.fetchall()
                result_list = []
                for row in results:
                    # Serialize each value to ensure JSON compatibility
                    serialized_row = {
                        columns[i]: SQLiteLoader._serialize_value(row[i])
                        for i in range(len(columns))
                    }
                    result_list.append(serialized_row)
            else:
                # This is an INSERT, UPDATE, DELETE, or other non-SELECT query
                affected_rows = cursor.rowcount
                sql_type = sql_query.strip().split()[0].upper()

                if sql_type in ['INSERT', 'UPDATE', 'DELETE']:
                    result_list = [{
                        "operation": sql_type,
                        "affected_rows": affected_rows,
                        "status": "success"
                    }]
                else:
                    # For other types of queries (CREATE, DROP, etc.)
                    result_list = [{
                        "operation": sql_type,
                        "status": "success"
                    }]

            # Commit the transaction for write operations
            conn.commit()

            # Close database connection
            cursor.close()
            conn.close()

            return result_list

        except sqlite3.Error as e:
            # Rollback in case of error
            if 'conn' in locals():
                conn.rollback()
                cursor.close()
                conn.close()
            raise SQLiteConnectionError(f"SQLite query execution error: {str(e)}") from e
        except Exception as e:
            # Rollback in case of error
            if 'conn' in locals():
                conn.rollback()
                cursor.close()
                conn.close()
            raise SQLiteQueryError(f"Error executing SQL query: {str(e)}") from e
