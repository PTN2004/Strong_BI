"""PostgreSQL loader for loading database schemas into FalkorDB graphs."""

import re
import datetime
import decimal
import logging
from typing import AsyncGenerator, Dict, Any, List, Tuple
from urllib.parse import urlparse, parse_qs, unquote

import psycopg2
from psycopg2 import sql
import tqdm

from api.loaders.base_loader import BaseLoader  # pylint: disable=import-error
from api.loaders.graph_loader import load_to_graph  # pylint: disable=import-error
from api.core.db_pool import pool_manager


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


class PostgreSQLQueryError(Exception):
    """Exception raised when PostgreSQL query execution fails."""


class PostgreSQLConnectionError(Exception):
    """Exception raised when PostgreSQL connection fails."""


class PostgresLoader(BaseLoader):

    SCHEMA_MODIFYING_OPERATIONS = {
        'CREATE', 'ALTER', 'DROP', 'RENAME', 'TRUNCATE'
    }

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
        r'^\s*CREATE\s+SCHEMA',
        r'^\s*DROP\s+SCHEMA',
    ]

    @staticmethod
    def _execute_sample_query(
        cursor: Any, table_name: str, col_name: str, sample_size: int = 3
    ) -> List[Any]:
        query = sql.SQL("""
            SELECT DISTINCT {col}
            FROM (
                SELECT {col}
                FROM {table}
                WHERE {col} IS NOT NULL
                LIMIT 1000
            ) AS sub
            LIMIT %s;
        """).format(
            col=sql.Identifier(col_name),
            table=sql.Identifier(table_name)
        )
        try:
            cursor.execute(query, (sample_size,))
            sample_results = cursor.fetchall()
            return [row[0] for row in sample_results if row[0] is not None]
        except Exception:
            return []

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        if isinstance(value, datetime.time):
            return value.isoformat()
        if isinstance(value, decimal.Decimal):
            return float(value)
        if value is None:
            return None
        return value

    @staticmethod
    def parse_schema_from_url(connection_url: str) -> str:
        try:
            parsed = urlparse(connection_url)
            query_params = parse_qs(parsed.query)

            options = query_params.get('options', [])
            if not options:
                return 'public'

            options_str = unquote(options[0])

            match = re.search(
                r'-c\s*search_path\s*=\s*([^\s,]+(?:\s*,\s*[^\s,]+)*)', options_str, re.IGNORECASE)
            if match:
                search_path = match.group(1)
                schemas = search_path.split(',')
                for s in schemas:
                    s = s.strip().strip('"\'')
                    if s and s != '$user':
                        return s
                return 'public'

            return 'public'

        except Exception:  
            return 'public'

    @staticmethod
    async def load(  
        prefix: str,
        connection_url: str,
        db=None,
    ) -> AsyncGenerator[tuple[bool, str], None]:
        conn = None
        cursor = None
        try:
            from api.core.pipeline import graph_name
            schema = PostgresLoader.parse_schema_from_url(connection_url)

            engine = pool_manager.get_engine(connection_url)
            conn = engine.raw_connection()
            cursor = conn.cursor()

            cursor.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )

            db_name = connection_url.split('/')[-1]
            if '?' in db_name:
                db_name = db_name.split('?')[0]

            yield True, "Extracting table information..."
            entities = PostgresLoader.extract_tables_info(cursor, schema)

            yield True, "Extracting relationship information..."
            relationships = PostgresLoader.extract_relationships(
                cursor, schema)

            cursor.close()
            cursor = None
            conn.close()
            conn = None

            yield True, "Loading data into graph..."
            await load_to_graph(graph_name(prefix, db_name), entities, relationships,
                                db_name=db_name, db_url=connection_url, db=db)

            yield True, (f"PostgreSQL schema loaded successfully. "
                         f"Found {len(entities)} tables.")

        except psycopg2.Error as e:
            logging.error("PostgreSQL connection error: %s", e)
            yield False, "Failed to connect to PostgreSQL database"
        except Exception as e:  
            logging.exception("Error loading PostgreSQL schema: %s", e)
            yield False, "Failed to load PostgreSQL database schema"
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()

    @staticmethod
    def extract_tables_info(cursor: Any, schema: str = 'public') -> Dict[str, Any]:
        entities = {}

        cursor.execute("""
            SELECT table_name, table_comment
            FROM information_schema.tables t
            LEFT JOIN (
                SELECT schemaname, tablename, description as table_comment
                FROM pg_tables pt
                JOIN pg_class pc ON pc.relname = pt.tablename
                JOIN pg_namespace pn ON pn.oid = pc.relnamespace AND pn.nspname = pt.schemaname
                JOIN pg_description pd ON pd.objoid = pc.oid AND pd.objsubid = 0
                WHERE pt.schemaname = %s
            ) tc ON tc.tablename = t.table_name
            WHERE t.table_schema = %s
            AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name;
        """, (schema, schema))

        tables = cursor.fetchall()

        for table_name, table_comment in tqdm.tqdm(tables, desc="Extracting table information"):
            table_name = table_name.strip()

            columns_info = PostgresLoader.extract_columns_info(
                cursor, table_name, schema)

            foreign_keys = PostgresLoader.extract_foreign_keys(
                cursor, table_name, schema)

            table_description = table_comment if table_comment else f"Table: {table_name}"

            col_descriptions = [col_info['description']
                                for col_info in columns_info.values()]

            entities[table_name] = {
                'description': table_description,
                'columns': columns_info,
                'foreign_keys': foreign_keys,
                'col_descriptions': col_descriptions
            }

        return entities

    @staticmethod
    def extract_columns_info(cursor: Any, table_name: str, schema: str = 'public') -> Dict[str, Any]:
        cursor.execute("""
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                CASE
                    WHEN pk.column_name IS NOT NULL THEN 'PRIMARY KEY'
                    WHEN fk.column_name IS NOT NULL THEN 'FOREIGN KEY'
                    ELSE 'NONE'
                END as key_type,
                COALESCE(pgd.description, '') as column_comment
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.constraint_schema = ku.constraint_schema
                WHERE tc.table_name = %s
                AND tc.table_schema = %s
                AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON pk.column_name = c.column_name
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.constraint_schema = ku.constraint_schema
                WHERE tc.table_name = %s
                AND tc.table_schema = %s
                AND tc.constraint_type = 'FOREIGN KEY'
            ) fk ON fk.column_name = c.column_name
            LEFT JOIN pg_namespace pn ON pn.nspname = c.table_schema
            LEFT JOIN pg_class pc ON pc.relname = c.table_name AND pc.relnamespace = pn.oid
            LEFT JOIN pg_attribute pa ON pa.attrelid = pc.oid AND pa.attname = c.column_name
            LEFT JOIN pg_description pgd ON pgd.objoid = pc.oid AND pgd.objsubid = pa.attnum
            WHERE c.table_name = %s
            AND c.table_schema = %s
            ORDER BY c.ordinal_position;
        """, (table_name, schema, table_name, schema, table_name, schema))

        columns = cursor.fetchall()
        columns_info = {}

        for col_name, data_type, is_nullable, column_default, key_type, column_comment in columns:
            col_name = col_name.strip()

            description_parts = []
            if column_comment:
                description_parts.append(column_comment)
            else:
                description_parts.append(
                    f"Column {col_name} of type {data_type}")

            if key_type != 'NONE':
                description_parts.append(f"({key_type})")

            if is_nullable == 'NO':
                description_parts.append("(NOT NULL)")

            if column_default:
                description_parts.append(f"(Default: {column_default})")

            sample_values = PostgresLoader.extract_sample_values_for_column(
                cursor, table_name, col_name
            )

            columns_info[col_name] = {
                'type': data_type,
                'null': is_nullable,
                'key': key_type,
                'description': ' '.join(description_parts),
                'default': column_default,
                'sample_values': sample_values
            }

        return columns_info

    @staticmethod
    def extract_foreign_keys(cursor: Any, table_name: str, schema: str = 'public') -> List[Dict[str, str]]:
        cursor.execute("""
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = %s
            AND tc.table_schema = %s;
        """, (table_name, schema))

        foreign_keys = []
        for constraint_name, column_name, foreign_table, foreign_column in cursor.fetchall():
            foreign_keys.append({
                'constraint_name': constraint_name.strip(),
                'column': column_name.strip(),
                'referenced_table': foreign_table.strip(),
                'referenced_column': foreign_column.strip()
            })

        return foreign_keys

    @staticmethod
    def extract_relationships(cursor: Any, schema: str = 'public') -> Dict[str, List[Dict[str, str]]]:
        cursor.execute("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = %s
            ORDER BY tc.table_name, tc.constraint_name;
        """, (schema,))

        relationships = {}
        for (table_name, constraint_name, column_name,
             foreign_table, foreign_column) in cursor.fetchall():
            table_name = table_name.strip()
            constraint_name = constraint_name.strip()

            if constraint_name not in relationships:
                relationships[constraint_name] = []

            relationships[constraint_name].append({
                'from': table_name,
                'to': foreign_table.strip(),
                'source_column': column_name.strip(),
                'target_column': foreign_column.strip(),
                'note': f'Foreign key constraint: {constraint_name}'
            })

        return relationships

    @staticmethod
    def is_schema_modifying_query(sql_query: str) -> Tuple[bool, str]:
        if not sql_query or not sql_query.strip():
            return False, ""

        normalized_query = sql_query.strip().upper()

        first_word = normalized_query.split(
        )[0] if normalized_query.split() else ""
        if first_word in PostgresLoader.SCHEMA_MODIFYING_OPERATIONS:
            for pattern in PostgresLoader.SCHEMA_PATTERNS:
                if re.match(pattern, normalized_query, re.IGNORECASE):
                    return True, first_word

            return True, first_word

        return False, ""

    @staticmethod
    async def refresh_graph_schema(graph_id: str, db_url: str, ) -> Tuple[bool, str]:
        try:
            logging.info("Schema modification detected. Refreshing graph schema.")
            from api.graph_db import GraphDatabaseFactory
            db_client = GraphDatabaseFactory.create()

            await db_client.connect()

            try:
                db_client.select_graph(graph_id)
                await db_client.clear_graph()
                parts = graph_id.split('_')
                if len(parts) >= 2:

                    prefix = '_'.join(parts[:-1])
                else:
                    prefix = graph_id

                    success, message = await PostgresLoader.load(prefix, db_url, db=db_client)

                    return success, message


            finally:
                await db_client.disconnect()

        except Exception as e:
            logging.error(f"Error refreshing graph schema: {str(e)}")
            return False, "Error refreshing graph schema"

    @staticmethod
    def execute_sql_query(sql_query: str, db_url: str) -> List[Dict[str, Any]]:
        try:
            engine = pool_manager.get_engine(db_url)
            conn = engine.raw_connection()
            cursor = conn.cursor()

            cursor.execute(sql_query)

            if cursor.description is not None:
                columns = [desc[0] for desc in cursor.description]
                results = cursor.fetchall()
                result_list = []
                for row in results:
                    serialized_row = {
                        columns[i]: PostgresLoader._serialize_value(row[i])
                        for i in range(len(columns))
                    }
                    result_list.append(serialized_row)
            else:
                affected_rows = cursor.rowcount
                sql_type = sql_query.strip().split()[0].upper()

                if sql_type in ['INSERT', 'UPDATE', 'DELETE']:
                    result_list = [{
                        "operation": sql_type,
                        "affected_rows": affected_rows,
                        "status": "success"
                    }]
                else:
                    result_list = [{
                        "operation": sql_type,
                        "status": "success"
                    }]

            conn.commit()

            cursor.close()
            conn.close()

            return result_list

        except psycopg2.Error as e:
            # Rollback in case of error
            if 'conn' in locals():
                conn.rollback()
                cursor.close()
                conn.close()
            raise PostgreSQLConnectionError(
                f"PostgreSQL query execution error: {str(e)}") from e
        except Exception as e:
            # Rollback in case of error
            if 'conn' in locals():
                conn.rollback()
                cursor.close()
                conn.close()
            raise PostgreSQLQueryError(
                f"Error executing SQL query: {str(e)}") from e
