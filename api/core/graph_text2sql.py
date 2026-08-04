import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Optional, TypedDict, List, Union
from langgraph.graph import StateGraph, START, END

from api.core.errors import InternalError
from api.core.pipeline import (
    auto_quote_sql_identifiers,
    detect_destructive_operation,
    format_ai_response,
    get_database_type_and_loader,
    graph_name,
    is_general_graph,
    validate_and_truncate_chat,
    validate_custom_model,
)
from api.agents import (
    AnalysisAgent,
    FollowUpAgent,
    HealerAgent,
    ChartAgent,
    DataAnalystAgent,
)
from api.retriever import Retriever
from api.core.text2sql import _build_query_result, _create_memory_tool, _Final


class AgentState(TypedDict):
    user_id: str
    graph_id: str
    chat_data: Any
    db: Any
    custom_api_key: str | None
    custom_model: str | None
    custom_api_base: str | None
    instructions: str | None
    use_user_rules: bool
    use_memory: bool
    
    # Context
    queries_history: list[str]
    result_history: list[str]
    db_description: str
    db_url: str
    db_type: str
    loader_class: Any
    schema_tables: list
    memory_context: str | None
    memory_tool: Any
    start_time: float
    
    # Control flow & results
    is_on_topic: bool
    relevancy_reason: str
    sql_query: str
    is_sql_translatable: bool
    missing_information: str
    ambiguities: str
    explanation: str
    is_destructive: bool
    
    query_results: list
    execution_error: str | None
    healing_attempts: int
    
    semantic_feedback: str | None
    validation_attempts: int
    
    follow_up_message: str | None
    chart_config: dict | None
    final_answer: str | None
    events_to_yield: list[dict] 


async def init_state(state: AgentState) -> dict:
    start_time = time.perf_counter()
    chat_data = state["chat_data"]
    user_id = state["user_id"]
    graph_id = state["graph_id"]
    db = state["db"]
    
    queries_history, result_history, instructions, use_user_rules = validate_and_truncate_chat(chat_data)
    custom_api_key = getattr(chat_data, "custom_api_key", None)
    custom_model = getattr(chat_data, "custom_model", None)
    custom_api_base = getattr(chat_data, "custom_api_base", None)
    use_memory = getattr(chat_data, "use_memory", False)
    validate_custom_model(custom_model)
    
    namespaced = graph_name(user_id, graph_id)
    retriever = Retriever(graph_id, db)
    db_description, db_url = await retriever.get_db_description()
    db_type, loader_class = get_database_type_and_loader(db_url)
    
    memory_context = None
    memory_tool = None
    if use_memory:
        memory_tool = await _create_memory_tool(user_id, namespaced, db=db)
        memory_context = await memory_tool.search_memories(query=queries_history[-1])
        
    return {
        "start_time": start_time,
        "queries_history": queries_history,
        "result_history": result_history,
        "instructions": instructions,
        "use_user_rules": use_user_rules,
        "custom_api_key": custom_api_key,
        "custom_model": custom_model,
        "custom_api_base": custom_api_base,
        "use_memory": use_memory,
        "db_description": db_description,
        "db_url": db_url,
        "db_type": db_type,
        "loader_class": loader_class,
        "memory_tool": memory_tool,
        "memory_context": memory_context,
        "healing_attempts": 0,
        "validation_attempts": 0,
        "events_to_yield": [{
            "type": "reasoning_step",
            "final_response": False,
            "message": "Step 1: Analyzing user query and generating SQL...",
        }]
    }



async def retrieve_schema(state: AgentState) -> dict:
    retriever = Retriever(state["graph_id"], state["db"])
    tables = await retriever.find(
        state["queries_history"], 
        state["db_description"],
        state["custom_api_key"],
        state["custom_model"],
        state["custom_api_base"]
    )
    return {"schema_tables": tables}

def analyze_query(state: AgentState) -> dict:
    agent_an = AnalysisAgent(
        state["queries_history"], state["result_history"], state["custom_api_key"], state["custom_model"], state["custom_api_base"]
    )
    
    instructions = state.get("instructions")
    if state.get("semantic_feedback"):
        instructions = (instructions or "") + f"\\n\\n[VALIDATOR FEEDBACK TO FIX PREVIOUS ATTEMPT]: {state['semantic_feedback']}"
        
    answer_an = agent_an.get_analysis(
        state["queries_history"][-1], state["schema_tables"], state["db_description"], 
        instructions, state["memory_context"], state["db_type"], None
    )
    
    sql_query = answer_an.get("sql_query", "")
    is_translatable = answer_an.get("is_sql_translatable", False)
    
    events = [{
        "type": "sql_query",
        "data": sql_query,
        "conf": answer_an.get("confidence", 0),
        "miss": answer_an.get("missing_information", ""),
        "amb": answer_an.get("ambiguities", ""),
        "exp": answer_an.get("explanation", ""),
        "is_valid": is_translatable,
        "final_response": False,
    }]
    
    if is_translatable:
        known_tables = {t[0] for t in state["schema_tables"]} if state["schema_tables"] else set()
        sql_query, was_modified = auto_quote_sql_identifiers(sql_query, known_tables, state["db_type"])
        _, is_destructive = detect_destructive_operation(sql_query)
        if is_destructive and is_general_graph(graph_name(state["user_id"], state["graph_id"])):
            is_translatable = False # Block it
            events.append({"type": "error", "final_response": True, "message": "Destructive operation not allowed on demo graphs"})

    return {
        "sql_query": sql_query,
        "is_sql_translatable": is_translatable,
        "missing_information": answer_an.get("missing_information", ""),
        "ambiguities": answer_an.get("ambiguities", ""),
        "explanation": answer_an.get("explanation", ""),
        "is_destructive": answer_an.get("is_destructive", False), # Approximation
        "events_to_yield": events
    }

def generate_follow_up(state: AgentState) -> dict:
    if not state.get("loader_class"):
        msg = "Unable to determine database type"
    elif not state.get("is_on_topic"):
        msg = "Off topic question: " + state.get("relevancy_reason", "")
    else:
        follow_up_agent = FollowUpAgent(
            state["queries_history"], state["result_history"], state["custom_api_key"], state["custom_model"], state["custom_api_base"]
        )
        msg = follow_up_agent.generate_follow_up_question(
            user_question=state["queries_history"][-1],
            analysis_result={"missing_information": state.get("missing_information"), "ambiguities": state.get("ambiguities")}
        )
        
    return {
        "follow_up_message": msg,
        "events_to_yield": [{
            "type": "followup_questions",
            "final_response": True,
            "message": msg,
            "missing_information": state.get("missing_information", ""),
            "ambiguities": state.get("ambiguities", ""),
        }]
    }

def execute_sql(state: AgentState) -> dict:
    events = [{"type": "reasoning_step", "final_response": False, "message": "Step 2: Executing SQL query"}]
    try:
        query_results = state["loader_class"].execute_sql_query(state["sql_query"], state["db_url"])
        events.append({"type": "query_result", "data": query_results, "final_response": False})
        return {"query_results": query_results, "execution_error": None, "events_to_yield": events}
    except Exception as e:
        events.append({"type": "reasoning_step", "final_response": False, "message": "SQL execution failed, preparing to heal..."})
        return {"execution_error": str(e), "events_to_yield": events}

def heal_sql(state: AgentState) -> dict:
    healer = HealerAgent(max_healing_attempts=3)
    def _run_sql(sql: str):
        return state["loader_class"].execute_sql_query(sql, state["db_url"])

    healing_result = healer.heal_and_execute(
        initial_sql=state["sql_query"],
        initial_error=state["execution_error"],
        execute_sql_func=_run_sql,
        db_description=state["db_description"],
        question=state["queries_history"][-1],
        database_type=state["db_type"],
    )
    
    events = []
    if not healing_result.get("success"):
        events.append({
            "type": "healing_failed", "final_response": False,
            "message": f"❌ Failed to heal query after {healing_result.get('attempts', 0)} attempt(s)",
            "final_error": healing_result.get("final_error", state["execution_error"]),
        })
        return {"healing_attempts": state["healing_attempts"] + healing_result.get("attempts", 1), "execution_error": healing_result.get("final_error"), "events_to_yield": events}
    else:
        events.append({
            "type": "healing_success", "final_response": False,
            "message": f"✅ Query healed and executed successfully after {healing_result.get('attempts', 0)} attempt(s)",
            "healed_sql": healing_result["sql_query"],
            "attempts": healing_result.get("attempts", 0),
        })
        events.append({"type": "query_result", "data": healing_result["query_results"], "final_response": False})
        return {
            "sql_query": healing_result["sql_query"],
            "query_results": healing_result["query_results"],
            "execution_error": None,
            "healing_attempts": state["healing_attempts"] + healing_result.get("attempts", 1),
            "events_to_yield": events
        }



def generate_chart(state: AgentState) -> dict:
    if not state.get("query_results"):
        return {}
        
    try:
        chart_agent = ChartAgent(custom_api_key=state["custom_api_key"], custom_model=state["custom_model"], custom_api_base=state["custom_api_base"])
        chart_config = chart_agent.generate_chart_config(
            user_query=state["queries_history"][-1],
            sql_query=state["sql_query"],
            query_results=state["query_results"]
        )
        if chart_config:
            return {
                "chart_config": chart_config,
                "events_to_yield": [{
                    "type": "chart_config",
                    "data": chart_config,
                    "final_response": False,
                }]
            }
    except Exception as e:
        logging.error(f"Chart generation error: {e}")
    return {}

def run_data_analyst(state: AgentState) -> dict:
    events = [{"type": "reasoning_step", "final_response": False, "message": "Step 4: Analyzing data with Code Interpreter..."}]
    
    if not state.get("query_results"):
        return {"events_to_yield": events}
        
    try:
        analyst = DataAnalystAgent(
            queries_history=state["queries_history"], 
            result_history=state["result_history"],
            custom_api_key=state.get("custom_api_key"), 
            custom_model=state.get("custom_model"), 
            custom_api_base=state.get("custom_api_base")
        )
        report = analyst.analyze_and_report(state["queries_history"][-1], state["query_results"])
        
        return {
            "final_answer": report,
            "events_to_yield": events
        }
    except Exception as e:
        logging.error(f"DataAnalyst Error: {e}")
        return {"events_to_yield": events}

def format_response(state: AgentState) -> dict:
    events = [{"type": "reasoning_step", "final_response": False, "message": "Step 5: Finalizing response..."}]
    
    if state.get("execution_error"):
        user_readable_response = f"Error executing SQL query: {state['execution_error']}"
        events.append({"type": "error", "final_response": True, "message": "Error executing SQL query"})
    else:
        if state.get("final_answer"):
            user_readable_response = state["final_answer"]
        else:
            results = state.get("query_results", [])
            num_rows = len(results) if isinstance(results, list) else 0
            if num_rows == 0:
                user_readable_response = "Truy vấn thành công nhưng không tìm thấy dữ liệu nào phù hợp với câu hỏi của bạn."
            else:
                user_readable_response = f"Dưới đây là kết quả phân tích dữ liệu cho câu hỏi của bạn (tìm thấy {num_rows} bản ghi):"
        events.append({"type": "ai_response", "final_response": True, "message": user_readable_response})
        
    return {"final_answer": user_readable_response, "events_to_yield": events}


def route_analysis(state: AgentState):
    if not state.get("is_sql_translatable"):
        return "follow_up"
    return "execute"

def route_execution(state: AgentState):
    if state.get("execution_error"):
        return "heal"
    return "chart"

def route_healing(state: AgentState):
    if state.get("execution_error") and state.get("healing_attempts", 0) >= 3:
        return "format" # Give up
    return "execute" # healed successfully or retrying

# Build Graph
builder = StateGraph(AgentState)
builder.add_node("init", init_state)
builder.add_node("retrieve", retrieve_schema)
builder.add_node("analysis", analyze_query)
builder.add_node("execute", execute_sql)
builder.add_node("heal", heal_sql)
builder.add_node("chart", generate_chart)
builder.add_node("data_analyst", run_data_analyst)
builder.add_node("format", format_response)
builder.add_node("follow_up", generate_follow_up)

builder.add_edge(START, "init")
builder.add_edge("init", "retrieve")
builder.add_edge("retrieve", "analysis")
builder.add_conditional_edges("analysis", route_analysis, {"follow_up": "follow_up", "execute": "execute"})
builder.add_conditional_edges("execute", route_execution, {"heal": "heal", "chart": "chart"})
builder.add_conditional_edges("heal", route_healing, {"format": "format", "execute": "chart"}) 
builder.add_edge("chart", "data_analyst")
builder.add_edge("data_analyst", "format")
builder.add_edge("format", END)
builder.add_edge("follow_up", END)

graph = builder.compile()

from api.core.ai_tracer import save_ai_trace
import traceback

def _make_json_safe(d: dict) -> dict:
    safe_d = {}
    for k, v in d.items():
        if k in ["db", "loader_class", "memory_tool"]:
            safe_d[k] = str(type(v))
        elif isinstance(v, (dict, list, str, int, float, bool, type(None))):
            safe_d[k] = v
        else:
            safe_d[k] = str(v)
    return safe_d

async def run_query_graph(user_id: str, graph_id: str, chat_data: Any, db: Optional[Any] = None) -> AsyncGenerator[Union[dict, _Final], None]:
    initial_state = {
        "user_id": user_id,
        "graph_id": graph_id,
        "chat_data": chat_data,
        "db": db,
    }
    
    current_state = dict(initial_state)
    graph_trace = {
        "initial_state": _make_json_safe(initial_state),
        "steps": []
    }
    
    try:
        async for event in graph.astream(initial_state, stream_mode="updates"):
            for node_name, state_updates in event.items():
                if isinstance(state_updates, dict):
                    # Log step state
                    graph_trace["steps"].append({
                        "node": node_name,
                        "updates": _make_json_safe(state_updates)
                    })
                    
                    current_state.update(state_updates)
                    if "events_to_yield" in state_updates:
                        for y_event in state_updates["events_to_yield"]:
                            yield y_event
    except Exception as e:
        graph_trace["steps"].append({
            "node": "CRITICAL_ERROR",
            "updates": {"error": str(e), "traceback": traceback.format_exc()}
        })
        raise
    finally:
        save_ai_trace("LangGraph_Execution", {"user_id": user_id, "graph_id": graph_id}, graph_trace)
    
    # After graph finishes, we need to return the _Final result exactly like original pipeline
    final_state = current_state
    
    yield _Final(_build_query_result(
        sql_query=final_state.get("sql_query", ""),
        results=final_state.get("query_results", []),
        ai_response=final_state.get("final_answer") or final_state.get("follow_up_message", ""),
        confidence=0.0, # approximation
        is_valid=final_state.get("is_sql_translatable", False),
        is_destructive=final_state.get("is_destructive", False),
        execution_time=time.perf_counter() - final_state.get("start_time", time.perf_counter()),
        missing_information=final_state.get("missing_information", ""),
        ambiguities=final_state.get("ambiguities", ""),
        explanation=final_state.get("explanation", ""),
        chart_config=final_state.get("chart_config"),
        error_message=final_state.get("execution_error"),
    ))
