import asyncio
import contextvars
import logging
import os
from typing import Any, Optional, Type

from api.agents import ResponseFormatterAgent
from api.config import Config
from api.graph_db import GraphDatabaseFactory
from api.core.errors import InvalidArgumentError
from api.loaders.postgres_loader import PostgresLoader
from api.loaders.mysql_loader import MySQLLoader
from api.loaders.sqlite_loader import SQLiteLoader
from api.loaders.base_loader import BaseLoader
from api.sql_utils import SQLIdentifierQuoter, DatabaseSpecificQuoter


MESSAGE_DELIMITER = "|||STRONG_BI_MESSAGE_BOUNDARY|||"

GENERAL_PREFIX = os.getenv("GENERAL_PREFIX")

_DESTRUCTIVE_VERBS = {
    'INSERT': 'Add new data to the database',
    'UPDATE': 'Modify existing data in the database',
    'DELETE': '**PERMANENTLY DELETE** data from the database',
    'DROP': '**PERMANENTLY DELETE** entire tables or database objects',
    'CREATE': 'Create new tables or database objects',
    'ALTER': 'Modify the structure of existing tables',
    'TRUNCATE': '**PERMANENTLY DELETE ALL DATA** from specified tables',
}

DESTRUCTIVE_OPS = frozenset(_DESTRUCTIVE_VERBS)

background_tasks_var: contextvars.ContextVar[Optional[set]] = (
    contextvars.ContextVar("strong_bi_background_tasks", default=None)
)


import re

def to_neo4j_safe(name: str) -> str:
    # Replace anything not alphanumeric, dot, or dash with dash
    safe_name = re.sub(r'[^a-zA-Z0-9\.\-]', '-', name.lower())
    # Must start with a letter
    if safe_name and not safe_name[0].isalpha():
        safe_name = f"db-{safe_name}"
    # Max length for Neo4j DB name is 63
    return safe_name[:63]

def graph_name(user_id: str, graph_id: str) -> str:
    graph_id = graph_id.strip()[:200]
    if not graph_id:
        raise InvalidArgumentError(
            "Invalid graph_id, must be a non-empty string up to 200 characters."
        )

    if GENERAL_PREFIX and graph_id.startswith(GENERAL_PREFIX):
        return to_neo4j_safe(graph_id)

    raw_name = f"{user_id}-{graph_id}"
    return to_neo4j_safe(raw_name)


def is_general_graph(graph_id: str) -> bool:
    return bool(GENERAL_PREFIX and graph_id.startswith(GENERAL_PREFIX))


def get_database_type_and_loader(
    db_url: str,
    *,
    sdk_only: bool = False,
) -> tuple[Optional[str], Optional[Type[BaseLoader]]]:
    if not db_url or db_url == "No URL available for this database.":
        return None, None

    db_url_lower = db_url.lower()

    if db_url_lower.startswith('postgresql://') or db_url_lower.startswith('postgres://'):
        return 'postgresql', PostgresLoader
    if db_url_lower.startswith('mysql://'):
        return 'mysql', MySQLLoader
    if db_url_lower.startswith('sqlite://') or db_url_lower.startswith('sqlite:') or db_url_lower.startswith('file'):
        return 'sqlite', SQLiteLoader

    if sdk_only:
        raise InvalidArgumentError(
            "Invalid database URL format. Must be PostgreSQL or MySQL."
        )
    return 'postgresql', PostgresLoader


def validate_custom_model(custom_model: Optional[str]) -> None:
    if not custom_model:
        return
    from api.config import SUPPORTED_VENDORS
    parts = custom_model.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise InvalidArgumentError(
            "Invalid model format. Expected 'vendor/model' (e.g. 'openai/gpt-4.1')"
        )
    if parts[0] not in SUPPORTED_VENDORS:
        raise InvalidArgumentError(
            f"Unsupported vendor '{parts[0]}'. Supported: {', '.join(SUPPORTED_VENDORS)}"
        )


def sanitize_query(query: str) -> str:
    return query.replace('\n', ' ').replace('\r', ' ')[:500]


def sanitize_log_input(value: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    return value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')


def truncate_for_log(query: str, max_length: int = 200) -> str:
    if len(query) > max_length:
        return query[:max_length] + "..."
    return query

def _strip_sql_comments_and_whitespace(sql_query: str) -> str:
    text = sql_query.lstrip()
    while text:
        if text.startswith("--"):
            newline = text.find("\n")
            if newline == -1:
                return ""
            text = text[newline + 1:].lstrip()
        elif text.startswith("/*"):
            end = text.find("*/")
            if end == -1:
                return ""
            text = text[end + 2:].lstrip()
        else:
            break
    return text


def detect_destructive_operation(sql_query: str) -> tuple[str, bool]:
    if not sql_query:
        return "", False
    cleaned = _strip_sql_comments_and_whitespace(sql_query)
    sql_type = cleaned.split()[0].upper() if cleaned else ""
    return sql_type, sql_type in DESTRUCTIVE_OPS


def auto_quote_sql_identifiers(
    sql_query: str,
    known_tables: set,
    db_type: Optional[str],
) -> tuple[str, bool]:
   
    quote_char = DatabaseSpecificQuoter.get_quote_char(db_type or 'postgresql')
    return SQLIdentifierQuoter.auto_quote_identifiers(
        sql_query, known_tables, quote_char
    )


def check_schema_modification(
    sql_query: str,
    loader_class: Type[BaseLoader],
) -> tuple[bool, str]:
    return loader_class.is_schema_modifying_query(sql_query)



def validate_and_truncate_chat(
    chat_data,
) -> tuple[list, Optional[list], Optional[str], bool]:
    queries_history = getattr(chat_data, 'chat', None)
    result_history = getattr(chat_data, 'result', None)
    instructions = getattr(chat_data, 'instructions', None)
    use_user_rules = getattr(chat_data, 'use_user_rules', True)

    if not queries_history or not isinstance(queries_history, list):
        raise InvalidArgumentError("Invalid or missing chat history")

    if len(queries_history) == 0:
        raise InvalidArgumentError("Empty chat history")

    if len(queries_history) > Config.SHORT_MEMORY_LENGTH:
        queries_history = queries_history[-Config.SHORT_MEMORY_LENGTH:]
        if result_history and len(result_history) > 0:
            max_results = Config.SHORT_MEMORY_LENGTH - 1
            if max_results > 0:
                result_history = result_history[-max_results:]
            else:
                result_history = []

    return queries_history, result_history, instructions, use_user_rules



async def quote_identifiers_from_graph(
    sql_query: str,
    graph_id: str,
    db_type: Optional[str],
    db=None,
    known_tables: Optional[set] = None,
) -> tuple[str, bool]:
    
    if known_tables is None:
        graph = GraphDatabaseFactory.create()
        try:
            await graph.connect()
            graph.select_graph(graph_id)
            try:
                tables_res = (
                    await graph.query("MATCH (t:Table) RETURN t.name")
                ).result_set
                known_tables = (
                    {row[0] for row in tables_res} if tables_res else set()
                )
            except Exception:  
                known_tables = set()
        finally:
            await graph.disconnect()
            

    return auto_quote_sql_identifiers(sql_query, known_tables, db_type)


def format_ai_response(  
    queries_history: list,
    result_history: Optional[list],
    sql_query: str,
    query_results: list,
    db_description: str,
    custom_api_key: Optional[str] = None,
    custom_model: Optional[str] = None,
    custom_api_base: Optional[str] = None,
) -> str:
    agent = ResponseFormatterAgent(
        queries_history, result_history, custom_api_key, custom_model, custom_api_base,
    )
    return agent.format_response(
        user_query=queries_history[-1] if queries_history else "",
        sql_query=sql_query,
        query_results=query_results,
        db_description=db_description,
    )


def build_destructive_confirmation_message(sql_type: str, sql_query: str) -> str:

    description = _DESTRUCTIVE_VERBS.get(sql_type, "Modify the database")
    return (
        "⚠️ DESTRUCTIVE OPERATION DETECTED ⚠️\n\n"
        f"The generated SQL query will perform a **{sql_type}** operation:\n\n"
        f"SQL:\n{sql_query}\n\n"
        f"What this will do:\n• {description}\n\n"
        "⚠️ WARNING: This operation will make changes to your database and "
        "may be irreversible."
    )


def save_memory_background(  
    memory_tool: Any,
    question: str,
    sql_query: str,
    success: bool,
    error: str,
    full_response: Optional[dict] = None,
    chat_histories: Optional[list] = None,
    task_sink: Optional[set] = None,
) -> None:

    sink = task_sink if task_sink is not None else background_tasks_var.get()

    def _track(task):
        if sink is None:
            return
        sink.add(task)
        task.add_done_callback(sink.discard)

    def _log_done(label: str):
        def _cb(task):
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                logging.error("%s failed: %s", label, exc)  # nosemgrep
            else:
                logging.info("%s completed successfully", label)
        return _cb

    save_query_task = asyncio.create_task(
        memory_tool.save_query_memory(
            query=question,
            sql_query=sql_query,
            success=success,
            error=error,
        )
    )
    _track(save_query_task)
    save_query_task.add_done_callback(_log_done("Query memory save"))

    if full_response is not None and chat_histories is not None:
        save_task = asyncio.create_task(
            memory_tool.add_new_memory(full_response, chat_histories)
        )
        _track(save_task)
        save_task.add_done_callback(_log_done("Memory save"))

    clean_task = asyncio.create_task(memory_tool.clean_memory())
    _track(clean_task)
    clean_task.add_done_callback(_log_done("Memory cleanup"))
