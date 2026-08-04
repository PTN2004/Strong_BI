import json
import logging
import time
from typing import Any, AsyncGenerator, Optional, TypedDict, List, Dict, Union
from langgraph.graph import StateGraph, START, END

from litellm import acompletion
from api.core.errors import InternalError
from api.core.text2sql import _build_query_result, _Final
from api.tools.database_tools import get_table_schema, search_all_tables, execute_test_sql, DATABASE_TOOLS_SCHEMA
from api.config import Config
from api.core.ai_tracer import save_ai_trace
from api.core.pipeline import get_database_type_and_loader, graph_name
from api.agents.utils import filter_thinking_process

logger = logging.getLogger(__name__)

class ReActState(TypedDict):
    user_id: str
    graph_id: str
    chat_data: Any
    db: Any
    db_url: str
    db_description: str
    loader_class: Any
    custom_api_key: Optional[str]
    custom_model: Optional[str]
    custom_api_base: Optional[str]
    queries_history: List[str]
    messages: List[Dict[str, Any]]
    final_sql: Optional[str]
    is_sql_translatable: bool
    events_to_yield: List[Dict[str, Any]]

SYSTEM_PROMPT = """
You are an expert SQL Data Analyst ReAct Agent.
Your job is to translate the user's question into a correct SQL query for their database.

You MUST use the provided tools to explore the database before writing the final SQL:
1. `search_all_tables`: Find out what tables exist.
2. `get_table_schema`: Get the exact column names, types, and foreign keys for tables you think are relevant.
3. `execute_test_sql`: Run a draft SQL query (with LIMIT 5) to see if it works and to inspect sample data.

Rules:
- NEVER guess table or column names. Always use tools to verify.
- You can call tools multiple times.
- Once you are 100% confident you have the correct SQL query that answers the user's question, output a final JSON object and NOTHING ELSE.

Final Output Format (when you are done):
```json
{
    "is_sql_translatable": true,
    "sql_query": "SELECT ...",
    "explanation": "Brief explanation of your logic"
}
```
If the question is completely unrelated to the database or impossible to answer:
```json
{
    "is_sql_translatable": false,
    "sql_query": "",
    "explanation": "Cannot be answered because..."
}
```
"""

async def init_react(state: ReActState) -> dict:
    from api.retriever import Retriever
    from api.core.text2sql import _create_memory_tool
    
    chat_data = state["chat_data"]
    user_id = state["user_id"]
    graph_id = state["graph_id"]
    db = state["db"]
    
    queries_history = [chat_data.query] if hasattr(chat_data, "query") else [chat_data.get("query", "")]
    
    retriever = Retriever(graph_id, db)
    db_description, db_url = await retriever.get_db_description()
    db_type, loader_class = get_database_type_and_loader(db_url)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n\nDatabase Description: {db_description}"},
        {"role": "user", "content": queries_history[-1]}
    ]
    
    return {
        "db_url": db_url,
        "db_description": db_description,
        "loader_class": loader_class,
        "queries_history": queries_history,
        "messages": messages,
        "custom_model": getattr(chat_data, "custom_model", None) or None,
        "custom_api_key": getattr(chat_data, "custom_api_key", None) or None,
        "custom_api_base": getattr(chat_data, "custom_api_base", None) or None,
        "events_to_yield": [{"type": "reasoning_step", "final_response": False, "message": "ReAct Agent initialized. Starting reasoning loop..."}]
    }

async def agent_node(state: ReActState) -> dict:
    model = state["custom_model"] or Config.COMPLETION_MODEL
    kwargs = {"temperature": 0.1, "tools": DATABASE_TOOLS_SCHEMA, "tool_choice": "auto"}
    if state["custom_api_key"]:
        kwargs["api_key"] = state["custom_api_key"]
    if state["custom_api_base"]:
        kwargs["api_base"] = state["custom_api_base"]
        
    try:
        response = await acompletion(
            model=model,
            messages=state["messages"],
            **kwargs
        )
        
        msg = response.choices[0].message
        message_dict = msg.model_dump()
        
        new_messages = list(state["messages"])
        
        # Litellm might not dump tool_calls cleanly if None
        if not message_dict.get("tool_calls"):
            message_dict.pop("tool_calls", None)
            
        new_messages.append(message_dict)
        
        events = []
        if message_dict.get("tool_calls"):
            events.append({"type": "reasoning_step", "final_response": False, "message": f"Agent is calling tools: {', '.join([tc['function']['name'] for tc in message_dict['tool_calls']])}"})
            return {"messages": new_messages, "events_to_yield": events}
            
        # If no tool calls, check if it's the final JSON
        content = filter_thinking_process(message_dict.get("content", ""))
        message_dict["content"] = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "{" in content and "}" in content:
            json_str = content[content.find("{"):content.rfind("}")+1]
        else:
            json_str = "{}"
            
        try:
            final_data = json.loads(json_str)
            events.append({"type": "reasoning_step", "final_response": False, "message": "Agent finalized SQL query."})
            return {
                "messages": new_messages,
                "final_sql": final_data.get("sql_query", ""),
                "is_sql_translatable": final_data.get("is_sql_translatable", False),
                "explanation": final_data.get("explanation", ""),
                "events_to_yield": events
            }
        except json.JSONDecodeError:
            # Force retry if invalid JSON
            events.append({"type": "reasoning_step", "final_response": False, "message": "Agent output invalid JSON. Retrying..."})
            new_messages.append({"role": "user", "content": "Your last response was not valid JSON. Please output ONLY valid JSON format."})
            return {"messages": new_messages, "events_to_yield": events}
            
    except Exception as e:
        logger.error(f"ReAct Agent Error: {e}")
        return {"events_to_yield": [{"type": "error", "final_response": True, "message": f"Agent error: {str(e)}"}]}

async def tool_node(state: ReActState) -> dict:
    last_message = state["messages"][-1]
    tool_calls = last_message.get("tool_calls", [])
    
    new_messages = list(state["messages"])
    events = []
    
    for tc in tool_calls:
        func_name = tc["function"]["name"]
        try:
            args = json.loads(tc["function"]["arguments"])
        except:
            args = {}
            
        result_str = ""
        try:
            if func_name == "search_all_tables":
                result_str = await search_all_tables(state["db"])
            elif func_name == "get_table_schema":
                result_str = await get_table_schema(state["db"], args.get("table_names", []))
            elif func_name == "execute_test_sql":
                result_str = execute_test_sql(state["loader_class"], state["db_url"], args.get("sql", ""))
            else:
                result_str = f"Unknown tool: {func_name}"
        except Exception as e:
            result_str = f"Tool Execution Error: {str(e)}"
            
        events.append({"type": "reasoning_step", "final_response": False, "message": f"Tool {func_name} executed."})
        
        new_messages.append({
            "role": "tool",
            "name": func_name,
            "tool_call_id": tc["id"],
            "content": result_str
        })
        
    return {"messages": new_messages, "events_to_yield": events}

def react_router(state: ReActState):
    last_message = state["messages"][-1]
    if last_message.get("tool_calls"):
        return "tools"
    return END

# Graph Definition
builder = StateGraph(ReActState)
builder.add_node("init", init_react)
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)

builder.add_edge(START, "init")
builder.add_edge("init", "agent")
builder.add_conditional_edges("agent", react_router, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

react_graph = builder.compile()

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

async def run_query_graph_v3(user_id: str, graph_id: str, chat_data: Any, db: Optional[Any] = None) -> AsyncGenerator[Union[dict, _Final], None]:
    start_time = time.perf_counter()
    initial_state = {
        "user_id": user_id,
        "graph_id": graph_id,
        "chat_data": chat_data,
        "db": db,
        "messages": [],
    }
    
    current_state = dict(initial_state)
    graph_trace = {"initial_state": _make_json_safe(initial_state), "steps": []}
    
    try:
        async for event in react_graph.astream(initial_state, stream_mode="updates"):
            for node_name, state_updates in event.items():
                if isinstance(state_updates, dict):
                    graph_trace["steps"].append({"node": node_name, "updates": _make_json_safe(state_updates)})
                    current_state.update(state_updates)
                    if "events_to_yield" in state_updates:
                        for y_event in state_updates["events_to_yield"]:
                            yield y_event
    finally:
        save_ai_trace("ReAct_Graph_v3_Execution", {"user_id": user_id, "graph_id": graph_id}, graph_trace)
    
    final_state = current_state
    
    # We should also execute the final SQL fully to get query_results
    final_sql = final_state.get("final_sql", "")
    query_results = []
    error_message = None
    if final_state.get("is_sql_translatable") and final_sql:
        try:
            query_results = final_state["loader_class"].execute_sql_query(final_sql, final_state["db_url"])
        except Exception as e:
            error_message = str(e)
    
    yield _Final(_build_query_result(
        sql_query=final_sql,
        results=query_results,
        ai_response=final_state.get("explanation", ""),
        confidence=0.9,
        is_valid=final_state.get("is_sql_translatable", False),
        is_destructive=False,
        execution_time=time.perf_counter() - start_time,
        missing_information="",
        ambiguities="",
        explanation=final_state.get("explanation", ""),
        chart_config=None,
        error_message=error_message,
    ))
