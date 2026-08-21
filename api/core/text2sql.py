import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Optional, Union

from pydantic import BaseModel
from redis import ResponseError, RedisError

from api.core.errors import GraphNotFoundError, InternalError, InvalidArgumentError
from api.core.schema_loader import load_database
from api.core.pipeline import (
    auto_quote_sql_identifiers,
    build_destructive_confirmation_message,
    check_schema_modification,
    detect_destructive_operation,
    format_ai_response,
    get_database_type_and_loader,
    graph_name,
    is_general_graph,
    quote_identifiers_from_graph,
    sanitize_log_input,
    sanitize_query,
    save_memory_background,
    validate_and_truncate_chat,
    validate_custom_model,
)
from api.agents import AnalysisAgent, RelevancyAgent, FollowUpAgent
from api.agents.healer_agent import HealerAgent
from api.agents.chart_agent import ChartAgent
from api.core.db_resolver import resolver_db
from api.core.result_models import QueryAnalyst, QueryMetadata, QueryResult, RefreshResult
from api.retriever import Retriever
from api.core.ai_tracer import save_ai_trace


async def _create_memory_tool(user_id: str, graph_id: str, db=None):
    from api.memory.graphiti_tool import MemoryTool
    return await MemoryTool.create(user_id, graph_id, db=db)


class GraphData(BaseModel):
    database: str


class ChatRequest(BaseModel):
    chat: list[str]
    result: list[str] | None = None
    instructions: str | None = None
    custom_api_key: str | None = None
    custom_model: str | None = None
    custom_api_base: str | None = None
    use_user_rules: bool = True  
    use_memory: bool = True


class ConfirmRequest(BaseModel):
    sql_query: str
    confirmation: str = ""
    chat: list = []
    custom_api_key: str | None = None
    custom_model: str | None = None
    custom_api_base: str | None = None
    use_memory: bool = False



async def get_schema(user_id: str, graph_id: str, db=None):
    namespaced = graph_name(user_id, graph_id)
    graph = None
    try:
        if db is not None:
            graph = db
        else:
            from api.graph_db.factory import GraphDatabaseFactory
            graph = await GraphDatabaseFactory.get_instance()
            
        graph.select_graph(namespaced)
    except Exception as e:  
        logging.error("Failed to select graph %s: %s", sanitize_log_input(namespaced), e)
        raise GraphNotFoundError("Graph not found or database error") from e

    try:
        tables_query = """
        MATCH (t:Table)
        OPTIONAL MATCH (c:Column)-[:BELONGS_TO]->(t)
        RETURN t.name AS table, collect(DISTINCT {name: c.name, type: c.type}) AS columns
        """

        links_query = """
        MATCH (src_col:Column)-[:BELONGS_TO]->(src_table:Table),
              (tgt_col:Column)-[:BELONGS_TO]->(tgt_table:Table),
              (src_col)-[:REFERENCES]->(tgt_col)
        RETURN DISTINCT src_table.name AS source, tgt_table.name AS target
        """

        metrics_query = """
        MATCH (m:Metric)
        RETURN m.name AS metric, m.description AS description, m.formula AS formula
        """

        dimensions_query = """
        MATCH (d:Dimension)
        RETURN d.name AS dimension, d.description AS description
        """

        metric_links_query = """
        MATCH (m:Metric)-[:CALCULATED_FROM]->(t:Table)
        RETURN m.name AS source, t.name AS target
        """

        dimension_links_query = """
        MATCH (d:Dimension)-[:BELONGS_TO_CONCEPT]->(c:Column)-[:BELONGS_TO]->(t:Table)
        RETURN DISTINCT d.name AS source, t.name AS target
        """

        try:
            tables_res = (await graph.query(tables_query)).result_set
            links_res = (await graph.query(links_query)).result_set
            metrics_res = (await graph.query(metrics_query)).result_set
            dimensions_res = (await graph.query(dimensions_query)).result_set
            metric_links_res = (await graph.query(metric_links_query)).result_set
            dimension_links_res = (await graph.query(dimension_links_query)).result_set
        except Exception as e:  
            logging.error("Error querying graph data for %s: %s", sanitize_log_input(namespaced), e)
            raise InternalError("Failed to read graph data") from e

        nodes = []
        for row in tables_res:
            try:
                table_name = row.get("table")
                columns = row.get("columns", [])
            except Exception:  
                continue
            
            if not table_name:
                continue

            if not isinstance(columns, list):
                columns = []

            normalized = []
            for col in columns:
                if not isinstance(col, dict):
                    continue
                    
                name = col.get("name")
                ctype = col.get("type")

                if name:
                    normalized.append({"name": name, "type": ctype})

            nodes.append({
                "id": table_name,
                "name": table_name,
                "label": "Table",
                "columns": normalized,
            })

        for row in metrics_res:
            metric_name = row.get("metric")
            if not metric_name:
                continue
            nodes.append({
                "id": metric_name,
                "name": metric_name,
                "label": "Metric",
                "description": row.get("description", ""),
                "formula": row.get("formula", ""),
            })

        for row in dimensions_res:
            dim_name = row.get("dimension")
            if not dim_name:
                continue
            nodes.append({
                "id": dim_name,
                "name": dim_name,
                "label": "Dimension",
                "description": row.get("description", ""),
            })

        links = []
        seen = set()
        
        # Combine all link results
        all_links = links_res + metric_links_res + dimension_links_res
        
        for row in all_links:
            source = row.get("source")
            target = row.get("target")
            
            if not source or not target:
                continue
                
            key = (source, target)
            if key in seen:
                continue
            seen.add(key)
            links.append({"source": source, "target": target})

        return {"nodes": nodes, "links": links}
    finally:
        pass


@dataclass(frozen=True)
class _Final:
    value: QueryResult


async def collect_result(
    gen: AsyncGenerator[Union[dict, _Final], None],
) -> QueryResult:
    async for event in gen:
        if isinstance(event, _Final):
            return event.value
    raise InternalError("Pipeline produced no final result")


async def _emit_schema_refresh(  
    loader_class,
    namespaced: str,
    db_url: str,
    operation_type: str,
    *,
    db: Optional[Any] = None,
    mark_final_response: bool = False,
) -> AsyncGenerator[dict, None]:
    
    base = {"final_response": False} if mark_final_response else {}
    yield {
        **base,
        "type": "reasoning_step",
        "message": "Step 3: Schema change detected - refreshing graph...",
    }

    refresh_success, refresh_message = await loader_class.refresh_graph_schema(
        namespaced, db_url, db=db,
    )
    if refresh_success:
        yield {
            **base,
            "type": "schema_refresh",
            "message": (
                f"✅ Schema change detected ({operation_type} operation)\n\n"
                "🔄 Graph schema has been automatically refreshed with the "
                "latest database structure."
            ),
            "refresh_status": "success",
        }
    else:
        yield {
            **base,
            "type": "schema_refresh",
            "message": (
                f"⚠️ Schema was modified but graph refresh failed: "
                f"{refresh_message}"
            ),
            "refresh_status": "failed",
        }


def _build_query_result(  
    sql_query: str,
    results: list,
    ai_response: str,
    *,
    confidence: float = 0.0,
    is_valid: bool = True,
    is_destructive: bool = False,
    requires_confirmation: bool = False,
    execution_time: float = 0.0,
    missing_information: str = "",
    ambiguities: str = "",
    explanation: str = "",
    chart_config: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> QueryResult:
    from api.core.result_models import ChartConfig
    
    parsed_chart_config = None
    if chart_config:
        parsed_chart_config = ChartConfig(
            chart_type=chart_config.get("chart_type", ""),
            option=chart_config.get("option", {})
        )

    return QueryResult(
        sql_result=sql_query,
        results=results,
        ai_response=ai_response,
        metadata=QueryMetadata(
            confidence=confidence,
            is_valid=is_valid,
            is_destructive=is_destructive,
            requires_confirmation=requires_confirmation,
            execution_time=execution_time,
        ),
        analysis=QueryAnalyst(
            missing_information=missing_information,
            ambiguities=ambiguities,
            explanation=explanation,
        ),
        chart_config=parsed_chart_config,
        error_message=error_message,
    )


async def run_query(  
    user_id: str,
    graph_id: str,
    chat_data: Any,
    db: Optional[Any] = None,
) -> AsyncGenerator[Union[dict, _Final], None]:
    
    retriever = Retriever(graph_id, db)
    
    overall_start = time.perf_counter()
    namespaced = graph_id
    queries_history, result_history, instructions, use_user_rules = (
        validate_and_truncate_chat(chat_data)
    )
    custom_api_key = getattr(chat_data, "custom_api_key", None)
    custom_model = getattr(chat_data, "custom_model", None)
    custom_api_base = getattr(chat_data, "custom_api_base", None)
    use_memory = getattr(chat_data, "use_memory", False)
    validate_custom_model(custom_model)

    logging.info("User Query: %s", sanitize_query(queries_history[-1]))

    
    memory_tool_task = (
        asyncio.create_task(_create_memory_tool(user_id, namespaced, db=db))
        if use_memory else None
    )

    yield {
        "type": "reasoning_step",
        "final_response": False,
        "message": "Step 1: Analyzing user query and generating SQL...",
    }

    db_description, db_url = await retriever.get_db_description()
    user_rules_spec = (
        await retriever.get_user_rules() if use_user_rules else None
    )
    db_type, loader_class = get_database_type_and_loader(db_url)

    if not loader_class:
        yield {"type": "error", "final_response": True,
               "message": "Unable to determine database type"}
        yield _Final(_build_query_result(
            sql_query="", results=[],
            ai_response="Unable to determine database type",
            is_valid=False,
            execution_time=time.perf_counter() - overall_start,
            error_message="Unable to determine database type",
        ))
        return

    find_task = asyncio.create_task(
        retriever.find(queries_history, db_description)
    )
    agent_rel = RelevancyAgent(
        queries_history, result_history, custom_api_key, custom_model, custom_api_base,
    )

    relevancy_task = asyncio.create_task(
        agent_rel.get_answer(queries_history[-1], db_description)
    )
    answer_rel = await relevancy_task
    
    await asyncio.to_thread(
        save_ai_trace,
        agent_name="RelevancyAgent",
        input_data={
            "queries_history": queries_history,
            "result_history": result_history,
            "db_description": db_description
        },
        output_data={
            "answer_rel": answer_rel
        }
    )

    if answer_rel["status"] != "On-topic":
        find_task.cancel()
        try:
            await find_task
        except asyncio.CancelledError:
            logging.debug("Find task cancelled (off-topic query)")
        msg = "Off topic question: " + answer_rel["reason"]
        yield {"type": "followup_questions", "final_response": True, "message": msg}
        yield _Final(_build_query_result(
            sql_query="", results=[], ai_response=msg,
            is_valid=False,
            execution_time=time.perf_counter() - overall_start,
        ))
        return

    tables = await find_task

    memory_tool = None
    memory_context = None
    if memory_tool_task is not None:
        memory_tool = await memory_tool_task
        memory_context = await memory_tool.search_memories(query=queries_history[-1])

    agent_an = AnalysisAgent(
        queries_history, result_history, custom_api_key, custom_model, custom_api_base,
    )
    answer_an = agent_an.get_analysis(
        queries_history[-1], tables, db_description, instructions, memory_context,
        db_type, user_rules_spec,
    )

        
    await asyncio.to_thread(
        save_ai_trace,
        agent_name="AnalysisAgent",
        input_data={
            "queries_history": queries_history[-1],
            "tables": tables,
            "db_description": db_description,
            "instructions": instructions,
            "memory_context": memory_context,
            
        },
        output_data={
            "answer_an": answer_an
        }
    )

    
    yield {
        "type": "sql_query",
        "data": answer_an.get("sql_query", ""),
        "conf": answer_an.get("confidence", 0),
        "miss": answer_an.get("missing_information", ""),
        "amb": answer_an.get("ambiguities", ""),
        "exp": answer_an.get("explanation", ""),
        "is_valid": answer_an.get("is_sql_translatable", False),
        "final_response": False,
    }

    if not answer_an.get("is_sql_translatable"):
        follow_up_agent = FollowUpAgent(
            queries_history, result_history, custom_api_key, custom_model, custom_api_base,
        )
        follow_up = follow_up_agent.generate_follow_up_question(
            user_question=queries_history[-1],
            analysis_result=answer_an,
        )
        yield {
            "type": "followup_questions",
            "final_response": True,
            "message": follow_up,
            "missing_information": answer_an.get("missing_information", ""),
            "ambiguities": answer_an.get("ambiguities", ""),
        }
        yield _Final(_build_query_result(
            sql_query=answer_an.get("sql_query", ""),
            results=[],
            ai_response=follow_up,
            confidence=answer_an.get("confidence", 0.0),
            is_valid=False,
            execution_time=time.perf_counter() - overall_start,
            missing_information=answer_an.get("missing_information", ""),
            ambiguities=answer_an.get("ambiguities", ""),
            explanation=answer_an.get("explanation", ""),
        ))
        return

    known_tables = {t[0] for t in tables} if tables else set()
    sanitized_sql, was_modified = auto_quote_sql_identifiers(
        answer_an["sql_query"], known_tables, db_type,
    )
    if was_modified:
        logging.info(
            "SQL query auto-sanitized: quoted table names with special characters"
        )
        answer_an["sql_query"] = sanitized_sql

    sql_query = answer_an["sql_query"]
    sql_type, is_destructive = detect_destructive_operation(sql_query)
    on_demo = is_general_graph(namespaced)

    if is_destructive and on_demo:
        yield {
            "type": "error",
            "final_response": True,
            "message": "Destructive operation not allowed on demo graphs",
        }
        yield _Final(_build_query_result(
            sql_query=sql_query, results=[],
            ai_response="Destructive operation not allowed on demo graphs",
            confidence=answer_an.get("confidence", 0.0),
            is_valid=True, is_destructive=True,
            execution_time=time.perf_counter() - overall_start,
            error_message="Destructive operation not allowed on demo graphs",
        ))
        return

    if is_destructive:
        confirmation_msg = build_destructive_confirmation_message(sql_type, sql_query)
        yield {
            "type": "destructive_confirmation",
            "message": confirmation_msg,
            "sql_query": sql_query,
            "operation_type": sql_type,
            "final_response": False,
        }
        yield _Final(_build_query_result(
            sql_query=sql_query, results=[], ai_response=confirmation_msg,
            confidence=answer_an.get("confidence", 0.0),
            is_valid=True, is_destructive=True, requires_confirmation=True,
            execution_time=time.perf_counter() - overall_start,
        ))
        return

    yield {
        "type": "reasoning_step",
        "final_response": False,
        "message": "Step 2: Executing SQL query",
    }

    is_schema_modifying, operation_type = check_schema_modification(sql_query, loader_class)

    execution_error_msg = None
    query_results: list = []
    user_readable_response = ""
    generated_chart_config = None

    try:
        try:
            query_results = loader_class.execute_sql_query(sql_query, db_url)
        except Exception as exec_error:  
            yield {
                "type": "reasoning_step",
                "final_response": False,
                "message": "Step 2a: SQL execution failed, attempting to heal query...",
            }
            healer = HealerAgent(max_healing_attempts=3)

            def _run_sql(sql: str):
                return loader_class.execute_sql_query(sql, db_url)

            healing_result = healer.heal_and_execute(
                initial_sql=sql_query,
                initial_error=str(exec_error),
                execute_sql_func=_run_sql,
                db_description=db_description,
                question=queries_history[-1],
                database_type=db_type,
            )

            if not healing_result.get("success"):
                yield {
                    "type": "healing_failed",
                    "final_response": False,
                    "message": (
                        f"❌ Failed to heal query after "
                        f"{healing_result.get('attempts', 0)} attempt(s)"
                    ),
                    "final_error": healing_result.get("final_error", str(exec_error)),
                }
                raise exec_error

            sql_query = healing_result["sql_query"]
            answer_an["sql_query"] = sql_query
            query_results = healing_result["query_results"]

            yield {
                "type": "healing_success",
                "final_response": False,
                "message": (
                    f"✅ Query healed and executed successfully after "
                    f"{healing_result.get('attempts', 0)} attempt(s)"
                ),
                "healed_sql": sql_query,
                "attempts": healing_result.get("attempts", 0),
            }

        if query_results:
            yield {
                "type": "query_result",
                "data": query_results,
                "final_response": False,
            }

            try:
                chart_agent = ChartAgent(custom_api_key=custom_api_key, custom_model=custom_model, custom_api_base=custom_api_base)
                chart_config = chart_agent.generate_chart_config(
                    user_query=queries_history[-1],
                    sql_query=sql_query,
                    query_results=query_results
                )
                if chart_config:
                    generated_chart_config = chart_config
                    yield {
                        "type": "chart_config",
                        "data": chart_config,
                        "final_response": False,
                    }
            except Exception as e:
                logging.error("Failed to generate chart config: %s", e)

        if is_schema_modifying:
            async for ev in _emit_schema_refresh(
                loader_class, namespaced, db_url, operation_type,
                db=db, mark_final_response=True,
            ):
                yield ev

        step_num = "4" if is_schema_modifying else "3"
        yield {
            "type": "reasoning_step",
            "final_response": False,
            "message": f"Step {step_num}: Generating user-friendly response",
        }

        user_readable_response = format_ai_response(
            queries_history=queries_history,
            result_history=result_history,
            sql_query=sql_query,
            query_results=query_results,
            db_description=db_description,
            custom_api_key=custom_api_key,
            custom_model=custom_model,
        )

        yield {
            "type": "ai_response",
            "final_response": True,
            "message": user_readable_response,
        }
    except Exception as e:  
        execution_error_msg = str(e)
        logging.error("Error executing SQL query: %s", str(e))  # nosemgrep
        yield {
            "type": "error",
            "final_response": True,
            "message": "Error executing SQL query",
        }
        if not user_readable_response:
            user_readable_response = f"Error executing SQL query: {execution_error_msg}"

    if memory_tool is not None:
        full_response = {
            "question": queries_history[-1],
            "generated_sql": answer_an.get("sql_query", ""),
            "answer": user_readable_response,
            "success": execution_error_msg is None,
        }
        if execution_error_msg:
            full_response["error"] = execution_error_msg
        save_memory_background(
            memory_tool=memory_tool,
            question=queries_history[-1],
            sql_query=answer_an.get("sql_query", ""),
            success=execution_error_msg is None,
            error=execution_error_msg or "",
            full_response=full_response,
            chat_histories=[queries_history, result_history],
        )

    yield _Final(_build_query_result(
        sql_query=answer_an.get("sql_query", ""),
        results=query_results if execution_error_msg is None else [],
        ai_response=user_readable_response,
        confidence=answer_an.get("confidence", 0.0),
        is_valid=True,
        is_destructive=is_destructive,
        execution_time=time.perf_counter() - overall_start,
        missing_information=answer_an.get("missing_information", ""),
        ambiguities=answer_an.get("ambiguities", ""),
        explanation=answer_an.get("explanation", ""),
        chart_config=generated_chart_config,
        error_message=execution_error_msg,
    ))


async def run_confirmed(  
    user_id: str,
    graph_id: str,
    confirm_data: Any,
    db: Optional[Any] = None,
) -> AsyncGenerator[Union[dict, _Final], None]:
    
    overall_start = time.perf_counter()
    namespaced = graph_name(user_id, graph_id)

    retiever = Retriever(graph_id=graph_id, db=db)
    
    if is_general_graph(namespaced):
        raise InvalidArgumentError(
            "Destructive operations are not allowed on demo graphs"
        )

    confirmation = (getattr(confirm_data, "confirmation", "") or "").strip().upper()
    sql_query = getattr(confirm_data, "sql_query", "") or ""
    queries_history = getattr(confirm_data, "chat", []) or []
    custom_api_key = getattr(confirm_data, "custom_api_key", None)
    custom_model = getattr(confirm_data, "custom_model", None)
    custom_api_base = getattr(confirm_data, "custom_api_base", None)
    validate_custom_model(custom_model)

    if not sql_query:
        raise InvalidArgumentError("No SQL query provided")

    question = (
        queries_history[-1] if queries_history else "Destructive operation confirmation"
    )

    if confirmation != "CONFIRM":
        yield {
            "type": "operation_cancelled",
            "message": (
                "Operation cancelled. The destructive SQL query was not executed."
            ),
        }
        yield _Final(_build_query_result(
            sql_query=sql_query, results=[],
            ai_response="Operation cancelled. The destructive SQL query was not executed.",
            is_valid=True, is_destructive=True,
            execution_time=time.perf_counter() - overall_start,
        ))
        return

    use_memory = bool(getattr(confirm_data, "use_memory", False))
    memory_tool = None
    execution_error_msg = None
    user_readable_response = ""
    query_results: list = []

    try:
        if use_memory:
            memory_tool = await _create_memory_tool(user_id, namespaced, db=db)
        db_description, db_url = await retiever.get_db_description(namespaced, db=db)
        db_type, loader_class = get_database_type_and_loader(db_url)

        if not loader_class:
            yield {"type": "error", "message": "Unable to determine database type"}
            yield _Final(_build_query_result(
                sql_query=sql_query, results=[],
                ai_response="Unable to determine database type",
                is_valid=False, is_destructive=True,
                execution_time=time.perf_counter() - overall_start,
                error_message="Unable to determine database type",
            ))
            return

        yield {"type": "reasoning_step",
               "message": "Step 2: Executing confirmed SQL query"}

        sql_query, was_modified = await quote_identifiers_from_graph(
            sql_query=sql_query, graph_id=namespaced, db_type=db_type, db=db,
        )
        if was_modified:
            logging.info("Confirmed SQL query auto-sanitized")

        is_schema_modifying, operation_type = check_schema_modification(
            sql_query, loader_class,
        )
        query_results = loader_class.execute_sql_query(sql_query, db_url)
        yield {"type": "query_result", "data": query_results}

        if is_schema_modifying:
            async for ev in _emit_schema_refresh(
                loader_class, namespaced, db_url, operation_type, db=db,
            ):
                yield ev

        step_num = "4" if is_schema_modifying else "3"
        yield {"type": "reasoning_step",
               "message": f"Step {step_num}: Generating user-friendly response"}

        user_readable_response = format_ai_response(
            queries_history=queries_history or [question],
            result_history=None,
            sql_query=sql_query,
            query_results=query_results,
            db_description=db_description,
            custom_api_key=custom_api_key,
            custom_model=custom_model,
        )

        yield {"type": "ai_response", "message": user_readable_response}

    except Exception as e:  
        # Wraps both MemoryTool.create failures and driver-specific execution errors.
        execution_error_msg = str(e) or "Error executing query"
        logging.error("Error executing confirmed SQL query: %s", str(e))  # nosemgrep
        yield {"type": "error", "message": execution_error_msg}
        if not user_readable_response:
            user_readable_response = execution_error_msg

    if memory_tool is not None:
        save_memory_background(
            memory_tool=memory_tool,
            question=question,
            sql_query=sql_query,
            success=execution_error_msg is None,
            error=execution_error_msg or "",
        )

    yield _Final(_build_query_result(
        sql_query=sql_query,
        results=query_results if execution_error_msg is None else [],
        ai_response=user_readable_response,
        is_valid=True, is_destructive=True,
        execution_time=time.perf_counter() - overall_start,
        error_message=execution_error_msg,
    ))



async def _resolve_refresh_target(
    user_id: str, graph_id: str, db: Optional[Any] = None,
) -> tuple[str, str]:
    retriever = Retriever(graph_id=graph_id, db=db)
    namespaced = graph_name(user_id, graph_id)
    if is_general_graph(namespaced):
        raise InvalidArgumentError("Demo graphs cannot be refreshed")

    _, db_url = await retriever.get_db_description()
    if not db_url or db_url == "No URL available for this database.":
        raise InternalError("No database URL found for this graph")

    return namespaced, db_url


async def refresh_database_schema(user_id: str, graph_id: str, db=None):
    try:
        _, db_url = await _resolve_refresh_target(user_id, graph_id, db=db)
        return await load_database(db_url, user_id, db=db)
    except (InvalidArgumentError, InternalError):
        raise
    except Exception as e:
        logging.error("Error in refresh_graph_schema: %s", str(e))
        raise InternalError("Internal server error while refreshing schema") from e


async def refresh_schema_for_sdk(
    user_id: str, graph_id: str, db: Optional[Any] = None,
) -> RefreshResult:
    from api.core.schema_loader import load_database_sync  

    try:
        _, db_url = await _resolve_refresh_target(user_id, graph_id, db=db)
    except InternalError as e:

        return RefreshResult(success=False, message=str(e))

    try:
        connection_result = await load_database_sync(db_url, user_id, db=db)
        return RefreshResult(
            success=connection_result.success,
            message=connection_result.message,
        )
    except (RedisError, ConnectionError, OSError) as e:
        logging.error("Error refreshing schema: %s", str(e))
        return RefreshResult(
            success=False,
            message=f"Failed to refresh schema: {str(e)}",
        )


async def delete_database(user_id: str, graph_id: str, db=None):
    """Delete the specified graph (namespaced to the user).

    This will attempt to delete the FalkorDB graph belonging to the
    authenticated user. The graph id used by the client is stripped of
    namespace and will be namespaced using the user's id from the request
    state.
    """
    namespaced = graph_name(user_id, graph_id)
    if is_general_graph(graph_id):
        raise InvalidArgumentError("Demo graphs cannot be deleted")

    try:
        if db is not None:
            db_instance = db
        else:
            from api.graph_db.factory import GraphDatabaseFactory
            db_instance = await GraphDatabaseFactory.get_instance()
            
        db_instance.select_graph(namespaced)
        await db_instance.clear_graph()
        return {"success": True, "graph": graph_id}
    except ResponseError as re:
        raise GraphNotFoundError("Failed to delete graph, Graph not found") from re
    except (RedisError, ConnectionError) as e:
        logging.exception("Failed to delete graph %s: %s", sanitize_log_input(namespaced), e)
        raise InternalError("Failed to delete graph") from e
    except Exception as e:  
        logging.exception(
            "Unexpected error deleting graph %s: %s", sanitize_log_input(namespaced), e,
        )
        raise InternalError("Failed to delete graph") from e

async def get_schema_metadata(user_id: str, graph_id: str, db=None):
    namespaced = graph_name(user_id, graph_id)
    try:
        if db is not None:
            graph = db
        else:
            from api.graph_db.factory import GraphDatabaseFactory
            graph = await GraphDatabaseFactory.get_instance()
            
        graph.select_graph(namespaced)
    except Exception as e:
        logging.error("Failed to select graph %s: %s", sanitize_log_input(namespaced), e)
        raise GraphNotFoundError("Graph not found or database error") from e

    try:
        query = """
        MATCH (t:Table)
        OPTIONAL MATCH (c:Column)-[:BELONGS_TO]->(t)
        RETURN t.name AS table, t.description AS description, collect(DISTINCT {name: c.name, type: c.type, description: c.description, key_type: c.key_type}) AS columns
        """
        res = await graph.query(query)
        metadata = []
        for row in res.result_set:
            if isinstance(row, dict):
                metadata.append({
                    "table_name": row.get("table", ""),
                    "description": row.get("description") or "",
                    "columns": row.get("columns") or []
                })
            else:
                metadata.append({
                    "table_name": row[0],
                    "description": row[1] or "",
                    "columns": row[2] or []
                })
        return metadata
    except Exception as e:
        logging.error("Error getting schema metadata: %s", str(e))
        raise InternalError("Failed to get schema metadata") from e


async def update_schema_metadata(user_id: str, graph_id: str, update_data: dict, db=None):
    namespaced = graph_name(user_id, graph_id)
    try:
        if db is not None:
            graph = db
        else:
            from api.graph_db.factory import GraphDatabaseFactory
            graph = await GraphDatabaseFactory.get_instance()
            
        graph.select_graph(namespaced)
    except Exception as e:
        logging.error("Failed to select graph %s: %s", sanitize_log_input(namespaced), e)
        raise GraphNotFoundError("Graph not found or database error") from e

    node_type = update_data.get("type")
    table_name = update_data.get("table_name")
    column_name = update_data.get("column_name")
    description = update_data.get("description", "")

    if not table_name:
        raise InvalidArgumentError("table_name is required")

    from api.config import Config
    import asyncio
    
    try:
        embedding_model = Config.EMBEDDING_MODEL
        embedding_result = await asyncio.to_thread(embedding_model.embed, description)
        if not embedding_result or not embedding_result[0]:
            raise InternalError("Failed to generate embedding for the new description")
        
        new_embedding = embedding_result[0]
        
        if node_type == "table":
            query = f"""
            MATCH (t:Table {{name: $table_name}})
            SET t.description = $desc, t.embedding = {graph.format_vector("embedding")}
            RETURN t.name
            """
            params = {
                "table_name": table_name,
                "desc": description,
                "embedding": new_embedding
            }
        elif node_type == "column":
            if not column_name:
                raise InvalidArgumentError("column_name is required for column update")
            query = f"""
            MATCH (t:Table {{name: $table_name}})<-[:BELONGS_TO]-(c:Column {{name: $column_name}})
            SET c.description = $desc, c.embedding = {graph.format_vector("embedding")}
            RETURN c.name
            """
            params = {
                "table_name": table_name,
                "column_name": column_name,
                "desc": description,
                "embedding": new_embedding
            }
        else:
            raise InvalidArgumentError("type must be 'table' or 'column'")

        res = await graph.query(query, params)
        if not res.result_set:
            raise InvalidArgumentError(f"{node_type.capitalize()} not found")
            
        return {"success": True, "message": "Metadata updated successfully"}
        
    except (InvalidArgumentError, InternalError):
        raise
    except Exception as e:
        logging.error("Error updating schema metadata: %s", str(e))
        raise InternalError(f"Failed to update schema metadata: {str(e)}") from e

