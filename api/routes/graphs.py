"""Graph-related routes for the text2sql API."""

import json
import logging
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from api.core.schema_loader import list_databases
from api.core.text2sql import (
    ChatRequest,
    ConfirmRequest,
    _Final,
    delete_database,
    get_schema,
    refresh_database_schema,
    run_confirmed,
    run_query,
)

from pydantic import BaseModel, Field
from api.core.graph_text2sql_v4 import run_query_graph_v4
from api.core.graph_text2sql_v4_5 import run_query_graph_v4_5
from api.core.graph_text2sql_v5 import run_query_graph_v5
from api.loaders.semantic_loader import load_semantic_layer, get_semantic_layer, delete_semantic_node
from api.core.pipeline import (
    GENERAL_PREFIX,
    MESSAGE_DELIMITER,
    graph_name,
    is_general_graph,
    validate_and_truncate_chat,
    validate_custom_model,
)
from api.core.errors import GraphNotFoundError, InternalError, InvalidArgumentError
from api.retriever import Retriever
from api.auth.user_management import token_required, roles_allowed, require_workspace
from api.graph_db.factory import GraphDatabaseFactory
from api.auth.models import UserRole
from api.routes.tokens import UNAUTHORIZED_RESPONSE


class SemanticMetric(BaseModel):
    name: str
    description: str = ""
    formula: str = ""
    table: str = ""


class SemanticDimension(BaseModel):
    name: str
    description: str = ""
    table: str = ""
    column: str = ""


class SemanticPayload(BaseModel):
    metrics: list[SemanticMetric] = Field(default_factory=list)
    dimensions: list[SemanticDimension] = Field(default_factory=list)


graphs_router = APIRouter(tags=["Graphs & Databases"])

def _get_model_with_prefix(user: dict) -> str | None:
    model = user.get("llm_model")
    provider = user.get("llm_provider")
    if not model:
        return None
    if provider and provider in ("openrouter", "openai", "anthropic", "cohere", "azure", "gemini"):
        if not model.startswith(f"{provider}/"):
            return f"{provider}/{model}"
    return model


async def _serialize_pipeline(gen):
    async for event in gen:
        if isinstance(event, _Final):
            return
        yield json.dumps(event) + MESSAGE_DELIMITER


def serialize_for_json(obj):
    """Recursively serialize Graph objects (Nodes, Edges) into dictionaries."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [serialize_for_json(v) for v in obj]
        
    # Check for FalkorDB / Neo4j Node
    if hasattr(obj, "id") and hasattr(obj, "labels") and hasattr(obj, "properties"):
        return {
            "id": getattr(obj, "id", None),
            "labels": list(getattr(obj, "labels", [])),
            "properties": getattr(obj, "properties", {})
        }
    # Check for FalkorDB Edge
    elif hasattr(obj, "id") and hasattr(obj, "relation") and hasattr(obj, "properties"):
        return {
            "id": getattr(obj, "id", None),
            "type": getattr(obj, "relation", "LINK"),
            "properties": getattr(obj, "properties", {}),
            "source": getattr(obj, "src_node", None),
            "target": getattr(obj, "dest_node", None)
        }
    # Check for Neo4j Edge
    elif hasattr(obj, "element_id") and hasattr(obj, "type") and hasattr(obj, "start_node"):
        return {
            "id": getattr(obj, "element_id", getattr(obj, "id", None)),
            "type": getattr(obj, "type", "LINK"),
            "properties": dict(obj) if hasattr(obj, "items") else getattr(obj, "_properties", {}),
            "source": getattr(getattr(obj, "start_node", None), "element_id", getattr(getattr(obj, "start_node", None), "id", None)),
            "target": getattr(getattr(obj, "end_node", None), "element_id", getattr(getattr(obj, "end_node", None), "id", None))
        }
    # Check for Neo4j Node
    elif hasattr(obj, "element_id") and hasattr(obj, "labels") and hasattr(obj, "items"):
        return {
            "id": getattr(obj, "element_id", getattr(obj, "id", None)),
            "labels": list(getattr(obj, "labels", [])),
            "properties": dict(obj)
        }
    
    # Fallback for primitive or unknown types
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)


class GraphData(BaseModel):
    database: str


class CypherRequest(BaseModel):
    query: str


@graphs_router.get(
    "",
    operation_id="list_databases",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
async def list_graphs(request: Request):
    graphs = await list_databases(request.state.workspace_id, GENERAL_PREFIX)
    return JSONResponse(content=graphs)


@graphs_router.get(
    "/{graph_id}/schema_metadata",
    operation_id="schema_metadata",
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def get_graph_schema_metadata(request: Request, graph_id: str):
    try:
        from api.core.text2sql import get_schema_metadata
        db = await GraphDatabaseFactory.get_instance()
        metadata = await get_schema_metadata(request.state.workspace_id, graph_id, db=db)
        return JSONResponse(content={"metadata": metadata})
    except GraphNotFoundError:
        return JSONResponse(content={"error": "Database not found"}, status_code=404)
    except Exception as e:
        logging.error("Error getting schema metadata: %s", str(e))
        return JSONResponse(content={"error": "Failed to get schema metadata"}, status_code=500)


@graphs_router.put(
    "/{graph_id}/schema_metadata",
    operation_id="update_schema_metadata",
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def update_graph_schema_metadata(request: Request, graph_id: str):
    try:
        data = await request.json()
        from api.core.text2sql import update_schema_metadata
        db = await GraphDatabaseFactory.get_instance()
        result = await update_schema_metadata(request.state.workspace_id, graph_id, data, db=db)
        return JSONResponse(content=result)
    except GraphNotFoundError:
        return JSONResponse(content={"error": "Database not found"}, status_code=404)
    except Exception as e:
        logging.error("Error updating schema metadata: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


@graphs_router.get(
    "/{graph_id}/data",
    operation_id="database_schema",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)

@token_required
@require_workspace
async def get_graph_data(
    request: Request, graph_id: str
):  

    try:
        db = await GraphDatabaseFactory.get_instance()
        schema = await get_schema(request.state.workspace_id, graph_id, db=db)
        return JSONResponse(content=schema)
    except GraphNotFoundError as gnfe:
        logging.warning("Graph not found: %s", str(gnfe))
        return JSONResponse(content={"error": "Database not found"}, status_code=404)
    except InternalError as ie:
        logging.error("Internal error getting schema: %s", str(ie))
        return JSONResponse(
            content={"error": "Failed to retrieve database schema"},
            status_code=500
        )


class SuggestQuestionsRequest(BaseModel):
    focus: str = ""
    custom_api_key: str | None = None
    custom_model: str | None = None
    custom_api_base: str | None = None


@graphs_router.post(
    "/{graph_id}/suggest_questions",
    operation_id="suggest_questions",
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
async def suggest_graph_questions(
    request: Request,
    graph_id: str,
    payload: SuggestQuestionsRequest = None,
):
    try:
        from api.agents.question_recommender_agent import QuestionRecommenderAgent
        from api.core.text2sql import get_schema_metadata
        
        db = await GraphDatabaseFactory.get_instance()
        metadata = await get_schema_metadata(request.state.workspace_id, graph_id, db=db)
        
        # Build schema summary for the agent
        tables_desc = []
        if isinstance(metadata, dict):
            for tbl_name, tbl_info in metadata.items():
                if isinstance(tbl_info, dict):
                    cols = tbl_info.get("columns", [])
                    col_names = [c.get("name") if isinstance(c, dict) else str(c) for c in cols]
                    tables_desc.append(f"Table `{tbl_name}`: columns [{', '.join(col_names[:15])}]")
                elif isinstance(tbl_info, list):
                    tables_desc.append(f"Table `{tbl_name}`: columns [{', '.join(str(c) for c in tbl_info[:15])}]")
        
        schema_context = "\n".join(tables_desc) if tables_desc else "Orders, OrderItems, Products, Customers, Sales"
        
        # Build clean tables list for UI schema explorer
        tables_summary = []
        if isinstance(metadata, dict):
            for tbl_name, tbl_info in metadata.items():
                if isinstance(tbl_info, dict):
                    cols = tbl_info.get("columns", [])
                    col_names = [c.get("name") if isinstance(c, dict) else str(c) for c in cols]
                    tables_summary.append({
                        "name": tbl_name,
                        "columns_count": len(cols),
                        "sample_columns": col_names[:6],
                    })
                elif isinstance(tbl_info, list):
                    tables_summary.append({
                        "name": tbl_name,
                        "columns_count": len(tbl_info),
                        "sample_columns": [str(c) for c in tbl_info[:6]],
                    })

        focus = payload.focus if payload else ""
        custom_key = payload.custom_api_key if payload else None
        custom_model = payload.custom_model if payload else None
        custom_base = payload.custom_api_base if payload else None
        
        agent = QuestionRecommenderAgent(
            custom_model=custom_model,
            custom_api_key=custom_key,
            custom_api_base=custom_base,
        )
        recommendations = agent.recommend_questions(schema_context=schema_context, user_focus=focus)
        return JSONResponse(content={
            "recommendations": recommendations, 
            "graph_id": graph_id,
            "tables_summary": tables_summary,
        })
    except Exception as e:
        logging.error("Error suggesting questions: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


@graphs_router.post("", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def load_graph(
    request: Request, data: GraphData = None, file: UploadFile = File(None)
):  
    if data:  
        raise HTTPException(status_code=501, detail="JSONLoader is not implemented yet")
    elif file:
        filename = file.filename

        if filename.endswith(".json"):  
            raise HTTPException(
                status_code=501, detail="JSONLoader is not implemented yet"
            )

        elif filename.endswith(".xml"):
            raise HTTPException(
                status_code=501, detail="ODataLoader is not implemented yet"
            )

        elif filename.endswith(".csv"):
            raise HTTPException(
                status_code=501, detail="CSVLoader is not implemented yet"
            )
        else:
            raise HTTPException(status_code=415, detail="Unsupported file type")
    else:
        raise HTTPException(status_code=415, detail="Unsupported Content-Type")


@graphs_router.post(
    "/{graph_id}",
    operation_id="query_database",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        # Fallback to user-specific LLM config if not provided in request
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = _get_model_with_prefix(user)
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_id = graph_name(request.state.workspace_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query(request.state.workspace_id, graph_id, chat_data, db=db)
            ):
                yield chunk
        except Exception as e: 
            import traceback
            tb = traceback.format_exc()
            logging.exception("Streaming query failed")
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": f"Internal error while processing query: {str(e)}\n{tb}",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")





@graphs_router.post(
    "/{graph_id}/v4",
    operation_id="query_database_v4",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph_v4(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = _get_model_with_prefix(user)
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_id = graph_name(request.state.workspace_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    # Capture FULL trace (trước khi lọc quyền) để ghi log server-side cho admin trace
    from api.core.chat_log import ThreadCapture
    capture = ThreadCapture(
        thread_id=getattr(chat_data, "thread_id", None),
        user_id=request.state.user_id,
        user_email=request.state.user.get("email", ""),
        graph_id=graph_id,
        query=chat_data.chat[-1] if chat_data.chat else "",
    )
    # Gắn thêm workspace_id nếu mô hình DB log yêu cầu (hiện ThreadCapture chưa định nghĩa)
    if hasattr(capture, "workspace_id"):
        capture.workspace_id = request.state.workspace_id

    def _event_allowed(chunk: str) -> bool:
        try:
            event = json.loads(chunk.split(MESSAGE_DELIMITER)[0])
        except Exception:
            return True
        capture.record(event)
        return True

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query_graph_v4(request.state.workspace_id, graph_id, chat_data, db=db)
            ):
                if _event_allowed(chunk):
                    # Set engine_version for metrics if present
                    try:
                        event = json.loads(chunk.split(MESSAGE_DELIMITER)[0])
                        if event.get("type") == "metrics":
                            event["data"]["engine_version"] = "v4"
                            capture.record(event)
                    except Exception:
                        pass
                    yield chunk
            await capture.save()
        except Exception as e: 
            import traceback
            tb = traceback.format_exc()
            logging.exception("Streaming query failed")
            capture.record({"type": "error", "message": str(e)})
            await capture.save()
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": f"Internal error while processing query: {str(e)}",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")


@graphs_router.post(
    "/{graph_id}/v4_5",
    operation_id="query_database_v4_5",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@graphs_router.post(
    "/{graph_id}/v4.5",
    include_in_schema=False
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph_v4_5(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = _get_model_with_prefix(user)
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_id = graph_name(request.state.workspace_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    from api.core.chat_log import ThreadCapture
    capture = ThreadCapture(
        thread_id=getattr(chat_data, "thread_id", None),
        user_id=request.state.user_id,
        user_email=request.state.user.get("email", ""),
        graph_id=graph_id,
        query=chat_data.chat[-1] if chat_data.chat else "",
    )
    if hasattr(capture, "workspace_id"):
        capture.workspace_id = request.state.workspace_id

    def _event_allowed(chunk: str) -> bool:
        try:
            event = json.loads(chunk.split(MESSAGE_DELIMITER)[0])
        except Exception:
            return True
        capture.record(event)
        return True

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query_graph_v4_5(request.state.workspace_id, graph_id, chat_data, db=db)
            ):
                if _event_allowed(chunk):
                    try:
                        event = json.loads(chunk.split(MESSAGE_DELIMITER)[0])
                        if event.get("type") == "metrics":
                            event["data"]["engine_version"] = "v4.5"
                            capture.record(event)
                    except Exception:
                        pass
                    yield chunk
            await capture.save()
        except Exception as e: 
            import traceback
            tb = traceback.format_exc()
            logging.exception("Streaming query failed")
            capture.record({"type": "error", "message": str(e)})
            await capture.save()
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": f"Internal error while processing query: {str(e)}",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")


@graphs_router.post(
    "/{graph_id}/v5",
    operation_id="query_database_v5",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph_v5(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = _get_model_with_prefix(user)
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_id = graph_name(request.state.workspace_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    from api.core.chat_log import ThreadCapture
    capture = ThreadCapture(
        thread_id=getattr(chat_data, "thread_id", None),
        user_id=request.state.user_id,
        user_email=request.state.user.get("email", ""),
        graph_id=graph_id,
        query=chat_data.chat[-1] if chat_data.chat else "",
    )
    if hasattr(capture, "workspace_id"):
        capture.workspace_id = request.state.workspace_id

    def _event_allowed(chunk: str) -> bool:
        try:
            event = json.loads(chunk.split(MESSAGE_DELIMITER)[0])
        except Exception:
            return True
        
        # Inject engine_version for metrics
        if event.get("type") == "metrics":
            event["data"]["engine_version"] = "v5"
            
        capture.record(event)
        return True

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query_graph_v5(request.state.workspace_id, graph_id, chat_data, db=db)
            ):
                if _event_allowed(chunk):
                    yield chunk
            await capture.save()
        except Exception as e: 
            import traceback
            tb = traceback.format_exc()
            logging.exception("Streaming query failed")
            capture.record({"type": "error", "message": str(e)})
            await capture.save()
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": f"Internal error while processing query: {str(e)}\\n{tb}",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")

@graphs_router.post("/{graph_id}/confirm", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def confirm_destructive_operation(
    request: Request,
    graph_id: str,
    confirm_data: ConfirmRequest,
):
    """
    Handle user confirmation for destructive SQL operations.
    Requires authentication.
    """

    # Eager validation — see note on the query endpoint above.
    try:
        # Fallback to user-specific LLM config if not provided in request
        user = getattr(request.state, "user", {})
        if not confirm_data.custom_model and user.get("llm_model"):
            confirm_data.custom_model = _get_model_with_prefix(user)
            confirm_data.custom_api_key = user.get("llm_api_key")
            confirm_data.custom_api_base = user.get("llm_api_base")
            
        namespaced = graph_name(request.state.workspace_id, graph_id)
        if is_general_graph(namespaced):
            raise InvalidArgumentError(
                "Destructive operations are not allowed on demo graphs"
            )
        if not (getattr(confirm_data, "sql_query", "") or "").strip():
            raise InvalidArgumentError("No SQL query provided")
        validate_custom_model(getattr(confirm_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in destructive operation: %s", str(iae))
        return JSONResponse(content={"error": "Invalid confirmation request"}, status_code=400)

    async def stream():
        try:
            async for chunk in _serialize_pipeline(
                run_confirmed(request.state.workspace_id, graph_id, confirm_data)
            ):
                yield chunk
        except Exception: 
            logging.exception("Streaming confirmed-destructive query failed")
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": "Internal error while processing confirmation",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")


@graphs_router.post("/{graph_id}/refresh", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def refresh_graph_schema(request: Request, graph_id: str):
    try:
        db = await GraphDatabaseFactory.get_instance()
        generator = await refresh_database_schema(request.state.workspace_id, graph_id, db=db)
        return StreamingResponse(generator, media_type="application/json")
    except (InternalError, InvalidArgumentError) as e:
        if isinstance(e, InternalError):
            logging.error("Internal error refreshing schema: %s", str(e))
            error_message = "Failed to refresh database schema"
            status_code = 500
        else:
            logging.warning("Invalid argument refreshing schema: %s", str(e))
            error_message = "Invalid request to refresh schema"
            status_code = 400
        return JSONResponse(content={"error": error_message}, status_code=status_code)


@graphs_router.post(
    "/{graph_id}/cypher",
    operation_id="execute_cypher",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def execute_cypher(request: Request, graph_id: str, data: CypherRequest):
    try:
        namespaced = graph_name(request.state.workspace_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        
        from api.core.db_resolver import resolver_db
        graph = resolver_db(db)
        graph.select_graph(namespaced)
        
        res = await graph.query(data.query)
        
        # Serialize the result set to avoid un-serializable objects (like neo4j/FalkorDB Nodes)
        serialized_results = serialize_for_json(res.result_set)
        return JSONResponse(content={"results": serialized_results})
        
    except Exception as e:
        logging.error("Cypher execution error: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


@graphs_router.get(
    "/{graph_id}/explore",
    operation_id="explore_graph",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
async def explore_graph(request: Request, graph_id: str, limit: int = 100):
    try:
        namespaced = graph_name(request.state.workspace_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        
        from api.core.db_resolver import resolver_db
        graph = resolver_db(db)
        graph.select_graph(namespaced)
        
        # We query for some nodes and edges to visualize
        nodes_query = f"MATCH (n) RETURN n LIMIT {limit}"
        edges_query = f"MATCH ()-[r]->() RETURN r LIMIT {limit}"
        
        nodes_res = await graph.query(nodes_query)
        edges_res = await graph.query(edges_query)
        
        return JSONResponse(content={
            "nodes": serialize_for_json(nodes_res.result_set),
            "edges": serialize_for_json(edges_res.result_set)
        })
    except Exception as e:
        logging.error("Graph explore error: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


@graphs_router.delete("/{graph_id}", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def delete_graph(request: Request, graph_id: str):

    try:
        db = await GraphDatabaseFactory.get_instance()
        result = await delete_database(request.state.workspace_id, graph_id, db=db)
        return JSONResponse(content=result)

    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in delete: %s", str(iae))
        return JSONResponse(content={"error": "Invalid delete request"}, status_code=400)
    except GraphNotFoundError as gnfe:
        logging.warning("Graph not found for deletion: %s", str(gnfe))
        return JSONResponse(content={"error": "Database not found"}, status_code=404)
    except InternalError as ie:
        logging.error("Internal error deleting database: %s", str(ie))
        return JSONResponse(
            content={"error": "Failed to delete database"},
            status_code=500
        )


class UserRulesRequest(BaseModel):
    """User rules request model."""
    user_rules: str


@graphs_router.get("/{graph_id}/user-rules", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def get_graph_user_rules(request: Request, graph_id: str):
   
    try:
        full_graph_id = graph_name(request.state.workspace_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        retriever = Retriever(graph_id=full_graph_id, db=db)
        user_rules = await retriever.get_user_rules()
        logging.info("Retrieved user rules length: %d", len(user_rules) if user_rules else 0)
        return JSONResponse(content={"user_rules": user_rules})
    except GraphNotFoundError:
        return JSONResponse(content={"error": "Database not found"}, status_code=404)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error getting user rules: %s", str(e))
        return JSONResponse(content={"error": "Failed to get user rules"}, status_code=500)


@graphs_router.put("/{graph_id}/user-rules", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def update_graph_user_rules(request: Request, graph_id: str, data: UserRulesRequest):
    """Update user rules for the specified graph."""
    try:
        # Prevent modifying rules for demo databases
        if GENERAL_PREFIX and graph_id.startswith(GENERAL_PREFIX):
            return JSONResponse(
                content={"error": "Rules cannot be modified for demo databases"},
                status_code=403
            )

        logging.info(
            "Received request to update user rules, content length: %d", len(data.user_rules)
        )
        full_graph_id = graph_name(request.state.workspace_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        retriever = Retriever(graph_id=full_graph_id, db=db)
        
        await retriever.set_user_rules(full_graph_id, data.user_rules)
        logging.info("User rules updated successfully")
        return JSONResponse(content={"success": True, "user_rules": data.user_rules})
    except GraphNotFoundError:
        logging.error("Graph not found")
        return JSONResponse(content={"error": "Database not found"}, status_code=404)
    except Exception as e: 
        logging.error("Error updating user rules: %s", str(e))
        return JSONResponse(content={"error": "Failed to update user rules"}, status_code=500)


@graphs_router.post(
    "/{graph_id}/semantic",
    operation_id="upload_semantic_layer",
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def upload_semantic_layer_endpoint(
    request: Request, graph_id: str, payload: SemanticPayload
):
    """
    Upload semantic business logic (Metrics, Dimensions) for the graph.
    """
    try:
        namespaced = graph_name(request.state.workspace_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        
        # Chuyển payload sang dict cho semantic_loader
        await load_semantic_layer(namespaced, payload.model_dump(), db=db)
        
        return JSONResponse(
            content={"success": True, "message": "Semantic layer loaded successfully"}
        )
    except Exception as e:
        logging.exception("Failed to load semantic layer")
        return JSONResponse(
            content={"error": f"Failed to load semantic layer: {str(e)}"}, status_code=500
        )

@graphs_router.get(
    "/{graph_id}/semantic",
    operation_id="get_semantic_layer",
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def get_semantic_layer_endpoint(
    request: Request, graph_id: str
):
    """
    Retrieve semantic business logic (Metrics, Dimensions) for the graph.
    """
    try:
        namespaced = graph_name(request.state.workspace_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        
        data = await get_semantic_layer(namespaced, db=db)
        
        return JSONResponse(
            content=data
        )
    except Exception as e:
        logging.exception("Failed to retrieve semantic layer")
        return JSONResponse(
            content={"error": f"Failed to retrieve semantic layer: {str(e)}"}, status_code=500
        )

@graphs_router.delete(
    "/{graph_id}/semantic/{node_type}/{node_name}",
    operation_id="delete_semantic_node",
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def delete_semantic_node_endpoint(
    request: Request, graph_id: str, node_type: str, node_name: str
):
    """
    Delete a semantic node (metric or dimension) from the graph.
    """
    try:
        namespaced = graph_name(request.state.workspace_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        
        await delete_semantic_node(namespaced, node_type, node_name, db=db)
        
        return JSONResponse(
            content={"success": True, "message": f"{node_type} {node_name} deleted successfully"}
        )
    except Exception as e:
        logging.exception("Failed to delete semantic node")
        return JSONResponse(
            content={"error": f"Failed to delete semantic node: {str(e)}"}, status_code=500
        )
