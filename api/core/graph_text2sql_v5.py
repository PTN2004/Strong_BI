import asyncio
import logging
import time
import traceback
from typing import Any, AsyncGenerator, Optional, TypedDict, Union
from langgraph.graph import StateGraph, START, END
from datetime import datetime
import sqlglot

from api.core.errors import InternalError
from api.core.pipeline import (
    auto_quote_sql_identifiers,
    detect_destructive_operation,
    get_database_type_and_loader,
    graph_name,
    is_general_graph,
    validate_and_truncate_chat,
    validate_custom_model,
)
from api.core.retriever_v4 import RetrieverV4
from api.agents.insight_and_chart_agent import InsightAndChartAgent
from api.agents.healer_agent import HealerAgent
from api.agents.validator_agent import ValidatorAgent
from api.core.text2sql import _build_query_result, _Final
from api.agents.utils import run_completion

logger = logging.getLogger(__name__)

MESSAGE_DELIMITER = "\n\n"

class AgentState(TypedDict):
    user_id: str
    graph_id: str
    chat_data: Any
    db: Any
    custom_api_key: str | None
    custom_model: str | None
    custom_api_base: str | None
    instructions: str | None
    
    # Context
    queries_history: list[str]
    db_description: str
    db_url: str
    db_type: str
    loader_class: Any
    graph_context: str
    start_time: float
    
    # Control flow & results
    sql_query: str
    validation_error: str | None
    validation_attempts: int
    healing_attempts: int
    logic_validation_attempts: int
    is_destructive: bool
    
    query_results: list
    execution_error: str | None
    
    insight: str | None
    chart_config: dict | None
    final_answer: str | None
    events_to_yield: list[dict]
    
    # Token Tracking
    total_prompt_tokens: int
    total_completion_tokens: int
    api_calls_count: int

async def init_state(state: AgentState) -> dict:
    start_time = time.perf_counter()
    chat_data = state["chat_data"]
    user_id = state["user_id"]
    graph_id = state["graph_id"]
    db = state["db"]
    
    queries_history, _, instructions, _ = validate_and_truncate_chat(chat_data)
    custom_api_key = getattr(chat_data, "custom_api_key", None)
    custom_model = getattr(chat_data, "custom_model", None)
    custom_api_base = getattr(chat_data, "custom_api_base", None)
    validate_custom_model(custom_model)
    
    # Quick DB resolution (using dummy description as graph context replaces it)
    from api.retriever import Retriever
    retriever_v2 = Retriever(graph_id, db)
    db_desc, db_url = await retriever_v2.get_db_description()
    db_type, loader_class = get_database_type_and_loader(db_url)
        
    return {
        "start_time": start_time,
        "queries_history": queries_history,
        "instructions": instructions,
        "custom_api_key": custom_api_key,
        "custom_model": custom_model,
        "custom_api_base": custom_api_base,
        "db_description": db_desc,
        "db_url": db_url,
        "db_type": db_type,
        "loader_class": loader_class,
        "validation_attempts": 0,
        "healing_attempts": 0,
        "logic_validation_attempts": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "api_calls_count": 0,
        "events_to_yield": [{
            "type": "reasoning_step",
            "final_response": False,
            "message": "Bước 1: Phân tích câu hỏi và thu thập ngữ nghĩa (Semantic GraphRAG)...",
        }]
    }

async def retrieve_schema(state: AgentState) -> dict:
    retriever = RetrieverV4(state["graph_id"], state["db"])
    question = state["queries_history"][-1]
    
    graph_context, graph_data = await retriever.find_context(question)
    
    # Fallback to raw database schema if semantic layer is missing or empty
    if not graph_context or graph_context == "No context found.":
        graph_context = f"Raw Database Schema (No Semantic Layer found):\n{state.get('db_description', 'No schema available.')}"
    
    events = [
        {"type": "reasoning_step", "final_response": False, "message": "Bước 2: Phân tích Cấu trúc Đồ thị (Graph Lineage)..."},
        {"type": "reasoning_graph", "final_response": False, "data": graph_data},
        {"type": "reasoning_step", "final_response": False, "message": "Bước 3: Sinh SQL dựa trên Ngữ nghĩa Kinh doanh..."}
    ]
    
    return {"graph_context": graph_context, "events_to_yield": events}

def generate_sql(state: AgentState) -> dict:
    question = state["queries_history"][-1]
    context = state["graph_context"]
    instructions = state.get("instructions", "")
    val_error = state.get("validation_error")
    
    system_prompt = f"""You are an elite SQL Developer and Data Engineer. Your task is to translate a user's natural language question into a syntactically correct and highly optimized SQL query based STRICTLY on the provided Semantic & Database Context.
Target Database Dialect: {state['db_type']}

### SEMANTIC & SCHEMA CONTEXT:
You will be provided with either a Semantic Layer (Metrics and Dimensions) or a Raw Database Schema.
- A "Metric" represents a quantitative measure with a predefined SQL formula (e.g., SUM(revenue)).
- A "Dimension" represents an attribute to group or filter by (e.g., created_at, country).

### STRICT RULES:
1. **Semantic Compliance**: If the user asks for concepts defined in the Context, you MUST use the exact formula, table, or column provided. Do not guess or invent column names.
2. **Aggregation & Grouping**: When querying a Metric alongside a Dimension, ensure proper aggregation and include a `GROUP BY` clause for the Dimension.
3. **Human Readable Results**: When selecting or grouping by a dimension (like area, store, staff, product), you MUST ALWAYS select their human-readable name columns (e.g., `area_name`, `customer_name`, `staff_name`, `product_name`) in addition to their IDs. Never return only IDs.
4. **Table Joins**: If querying across multiple tables, infer the correct `JOIN` paths from the schema structure or foreign keys. Use appropriate table aliases (e.g., `orders o`).
5. **Dialect Specifics**: Ensure all functions (e.g., date handling, string manipulation, casting) are 100% compatible with {state['db_type']}.
6. **No Hallucinations**: Do NOT query tables or columns that do not exist in the Context. If a column is missing, rely on what is available.
7. **Performance**: Avoid `SELECT *`. Only select the columns necessary to answer the question. Apply `LIMIT` if the user asks for "top N" or "best".
8. **Output Format**: Return ONLY the raw executable SQL query. Do not wrap it in markdown code blocks like ```sql or ```. Do not provide any explanations. Do not use quotes around the entire string.
9. **Date Context**: Today is {datetime.now().strftime('%Y-%m-%d')}. When the user asks for relative dates (e.g. 'this month', 'today', 'August'), assume this current year/month unless otherwise specified.

### RESPONSE FORMAT:
SELECT ...
FROM ...
WHERE ...
"""

    user_prompt = f"""### PROVIDED CONTEXT:
{context}

### USER INSTRUCTIONS:
{instructions if instructions else 'None'}

### USER QUESTION:
{question}

Please generate the corresponding {state['db_type']} SQL query:"""
    
    if val_error:
        user_prompt += f"\n\n[PREVIOUS ATTEMPT FAILED WITH ERROR/FEEDBACK]: {val_error}\nPlease fix the SQL syntax/logic and try again."
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    sql, usage = run_completion(
        messages=messages,
        custom_model=state["custom_model"],
        custom_api_key=state["custom_api_key"],
        temperature=0.0,
        return_usage=True
    )
    sql = sql.strip()
    
    # Cleanup formatting if LLM still returned markdown
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    
    sql = sql.strip()
    
    return {
        "sql_query": sql,
        "events_to_yield": [{
            "type": "sql_query",
            "data": sql,
            "final_response": False,
        }],
        "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
        "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
        "api_calls_count": state.get("api_calls_count", 0) + 1
    }

def validate_sql(state: AgentState) -> dict:
    sql = state["sql_query"]
    events = []
    is_destructive = False
    error_msg = None
    
    # 1. Check destructive
    _, is_destructive = detect_destructive_operation(sql)
    if is_destructive and is_general_graph(state["graph_id"]):
        error_msg = "Destructive operation (INSERT/UPDATE/DELETE) not allowed on demo graphs."
    
    # 2. Syntax validation with sqlglot
    if not error_msg:
        try:
            # Map db_type to sqlglot dialects roughly
            dialect_map = {"postgres": "postgres", "mysql": "mysql", "sqlite": "sqlite", "snowflake": "snowflake"}
            dialect = dialect_map.get(state["db_type"], "postgres")
            sqlglot.parse_one(sql, read=dialect)
        except sqlglot.errors.ParseError as e:
            error_msg = f"Syntax Error: {str(e)}"
            
    if error_msg:
        events.append({"type": "reasoning_step", "final_response": False, "message": f"Phát hiện lỗi cú pháp: {error_msg}. Đang tự động sửa..."})
        return {
            "validation_error": error_msg,
            "validation_attempts": state.get("validation_attempts", 0) + 1,
            "is_destructive": is_destructive,
            "events_to_yield": events
        }
        
    events.append({"type": "reasoning_step", "final_response": False, "message": "Bước 3: Thực thi truy vấn SQL hợp lệ..."})
    return {
        "validation_error": None,
        "validation_attempts": state.get("validation_attempts", 0) + 1,
        "is_destructive": is_destructive,
        "events_to_yield": events
    }

async def execute_sql(state: AgentState) -> dict:
    events = []
    try:
        sql = state["sql_query"]
        try:
            dialect_map = {"postgres": "postgres", "mysql": "mysql", "sqlite": "sqlite", "snowflake": "snowflake"}
            dialect = dialect_map.get(state["db_type"], "postgres")
            parsed = sqlglot.parse_one(sql, read=dialect)
            if isinstance(parsed, sqlglot.exp.Select) and not parsed.args.get("limit"):
                parsed = parsed.limit(500)
                sql = parsed.sql(dialect=dialect)
                logger.info("Auto-appended LIMIT 500 to query")
        except Exception as e:
            logger.warning(f"Could not auto-append LIMIT: {e}")

        # Run DB query in a separate thread to not block the async event loop
        query_results = await asyncio.to_thread(
            state["loader_class"].execute_sql_query, sql, state["db_url"]
        )
        
        events.append({"type": "query_result", "data": query_results, "final_response": False})
        return {"query_results": query_results, "execution_error": None, "events_to_yield": events, "sql_query": sql}
    except Exception as e:
        events.append({"type": "reasoning_step", "final_response": False, "message": f"Lỗi thực thi DB: {str(e)}"})
        return {"execution_error": str(e), "events_to_yield": events}

def generate_insight_and_chart(state: AgentState) -> dict:
    events = [{"type": "reasoning_step", "final_response": False, "message": "Bước 4: Sinh Insight và Biểu đồ (Charting)..."}]
    
    if not state.get("query_results"):
        return {"events_to_yield": events}
        
    try:
        agent = InsightAndChartAgent(custom_api_key=state["custom_api_key"], custom_model=state["custom_model"], custom_api_base=state["custom_api_base"])
        res = agent.generate(
            user_query=state["queries_history"][-1],
            sql_query=state["sql_query"],
            query_results=state["query_results"],
            schema_context=state["graph_context"]
        )
        
        insight = res.get("insight") if res else None
        chart_config = res if res and res.get("should_visualize") else None
        
        if chart_config:
            events.append({"type": "chart_config", "data": chart_config.get("option"), "chart_type": chart_config.get("chart_type"), "final_response": False})
            
        usage = res.get("usage", {}) if res else {}
            
        return {
            "insight": insight,
            "chart_config": chart_config,
            "events_to_yield": events,
            "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
            "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
            "api_calls_count": state.get("api_calls_count", 0) + 1
        }
    except Exception as e:
        logging.error(f"Insight/Chart generation error: {e}")
        return {"events_to_yield": events}

def heal_sql(state: AgentState) -> dict:
    events = [{"type": "reasoning_step", "final_response": False, "message": f"Cố gắng sửa lỗi DB (Lần {state.get('healing_attempts', 0) + 1})..."}]
    agent = HealerAgent(custom_api_key=state["custom_api_key"], custom_model=state["custom_model"], custom_api_base=state["custom_api_base"])
    
    fixed_sql, usage = agent.heal(
        user_question=state["queries_history"][-1],
        broken_sql=state["sql_query"],
        error_message=state["execution_error"],
        schema_context=state["graph_context"]
    )
    
    if fixed_sql:
        events.append({"type": "reasoning_step", "final_response": False, "message": "Đã tạo câu lệnh sửa lỗi. Đang thực thi lại..."})
        return {
            "sql_query": fixed_sql,
            "healing_attempts": state.get("healing_attempts", 0) + 1,
            "execution_error": None, # clear error for next execute
            "events_to_yield": events,
            "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
            "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
            "api_calls_count": state.get("api_calls_count", 0) + 1
        }
    else:
        return {
            "healing_attempts": state.get("healing_attempts", 0) + 1,
            "events_to_yield": events,
            "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
            "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
            "api_calls_count": state.get("api_calls_count", 0) + 1
        }

def evaluate_logic(state: AgentState) -> dict:
    events = [{"type": "reasoning_step", "final_response": False, "message": f"Đánh giá Logic/Ngữ nghĩa kết quả (Lần {state.get('logic_validation_attempts', 0) + 1})..."}]
    agent = ValidatorAgent(
        queries_history=state["queries_history"],
        result_history=[],
        custom_api_key=state["custom_api_key"], 
        custom_model=state["custom_model"], 
        custom_api_base=state["custom_api_base"]
    )
    
    res = agent.validate(
        user_question=state["queries_history"][-1],
        sql_query=state["sql_query"],
        query_results=state.get("query_results", [])
    )
    
    usage = res.get("usage", {}) if res else {}
    if res and res.get("status") == "Invalid":
        feedback = res.get("feedback", res.get("reason", "Lỗi logic không xác định."))
        events.append({"type": "reasoning_step", "final_response": False, "message": f"Phát hiện lỗi Logic: {feedback}"})
        return {
            "validation_error": feedback,
            "logic_validation_attempts": state.get("logic_validation_attempts", 0) + 1,
            "events_to_yield": events,
            "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
            "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
            "api_calls_count": state.get("api_calls_count", 0) + 1
        }
    
    events.append({"type": "reasoning_step", "final_response": False, "message": "Kết quả hợp lệ về mặt ngữ nghĩa."})
    return {
        "validation_error": None,
        "events_to_yield": events,
        "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
        "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
        "api_calls_count": state.get("api_calls_count", 0) + 1
    }

def format_response(state: AgentState) -> dict:
    events = []
    
    if state.get("execution_error"):
        ans = f"Lỗi khi chạy SQL: {state['execution_error']}"
        events.append({"type": "error", "final_response": True, "message": ans})
    elif state.get("validation_error") and state.get("validation_attempts", 0) >= 3:
        ans = f"Không thể sinh SQL hợp lệ sau nhiều lần thử. Lỗi cuối: {state['validation_error']}"
        events.append({"type": "error", "final_response": True, "message": ans})
    else:
        results = state.get("query_results", [])
        num_rows = len(results) if isinstance(results, list) else 0
        
        if num_rows == 0:
            ans = "Truy vấn thành công nhưng không tìm thấy dữ liệu."
        else:
            ans = state.get("insight") or f"Đã tìm thấy {num_rows} bản ghi. (V5 Deep Analysis)"
            
        events.append({"type": "ai_response", "final_response": True, "message": ans})
        
    # Yield metrics event
    total_prompt = state.get("total_prompt_tokens", 0)
    total_comp = state.get("total_completion_tokens", 0)
    api_calls = state.get("api_calls_count", 0)
    
    from api.pricing.pricing import calculate_cost
    model_name = state.get("custom_model")
    cost_usd = calculate_cost(model_name, total_prompt, total_comp) if model_name else 0.0
    
    events.append({
        "type": "metrics",
        "data": {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_comp,
            "total_tokens": total_prompt + total_comp,
            "cost_usd": cost_usd,
            "api_calls_count": api_calls
        },
        "final_response": False
    })
        
    return {"final_answer": ans, "events_to_yield": events}

def route_validation(state: AgentState):
    if state.get("validation_error"):
        if state.get("validation_attempts", 0) >= 3:
            return "format" # Give up after 3 retries
        return "generate_sql" # Feedback loop
    return "execute"

def route_execution(state: AgentState):
    if state.get("execution_error"):
        if state.get("healing_attempts", 0) >= 3:
            return "format"
        return "heal_sql"
    return "evaluate_logic"

def route_logic_evaluation(state: AgentState):
    if state.get("validation_error"):
        if state.get("logic_validation_attempts", 0) >= 3:
            return "insight_chart" # Proceed to show the best we got
        return "generate_sql"
    return "insight_chart"

# Build Graph V5
builder = StateGraph(AgentState)
builder.add_node("init", init_state)
builder.add_node("retrieve", retrieve_schema)
builder.add_node("generate_sql", generate_sql)
builder.add_node("validate_sql", validate_sql)
builder.add_node("execute", execute_sql)
builder.add_node("heal_sql", heal_sql)
builder.add_node("evaluate_logic", evaluate_logic)
builder.add_node("insight_chart", generate_insight_and_chart)
builder.add_node("format", format_response)

builder.add_edge(START, "init")
builder.add_edge("init", "retrieve")
builder.add_edge("retrieve", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")
builder.add_conditional_edges("validate_sql", route_validation, {"generate_sql": "generate_sql", "format": "format", "execute": "execute"})
builder.add_conditional_edges("execute", route_execution, {"format": "format", "heal_sql": "heal_sql", "evaluate_logic": "evaluate_logic"})
builder.add_edge("heal_sql", "execute")
builder.add_conditional_edges("evaluate_logic", route_logic_evaluation, {"generate_sql": "generate_sql", "insight_chart": "insight_chart"})
builder.add_edge("insight_chart", "format")
builder.add_edge("format", END)

graph = builder.compile()

from api.core.ai_tracer import save_ai_trace

def _make_json_safe(d: dict) -> dict:
    safe_d = {}
    for k, v in d.items():
        if k in ["db", "loader_class"]:
            safe_d[k] = str(type(v))
        elif isinstance(v, (dict, list, str, int, float, bool, type(None))):
            safe_d[k] = v
        else:
            safe_d[k] = str(v)
    return safe_d

async def run_query_graph_v5(user_id: str, graph_id: str, chat_data: Any, db=None) -> AsyncGenerator[Union[dict, _Final], None]:
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
        save_ai_trace("LangGraph_Execution_V4", {"user_id": user_id, "graph_id": graph_id}, graph_trace)
    
    final_state = current_state
    
    yield _Final(_build_query_result(
        sql_query=final_state.get("sql_query", ""),
        results=final_state.get("query_results", []),
        ai_response=final_state.get("final_answer", ""),
        confidence=1.0 if not final_state.get("execution_error") else 0.0,
        is_valid=final_state.get("validation_error") is None,
        is_destructive=final_state.get("is_destructive", False),
        execution_time=time.perf_counter() - final_state.get("start_time", time.perf_counter()),
        missing_information="",
        ambiguities="",
        explanation="",
        chart_config=final_state.get("chart_config"),
        error_message=final_state.get("execution_error") or final_state.get("validation_error"),
    ))
