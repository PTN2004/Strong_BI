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
from api.core.graph_text2sql import run_query_graph
from api.core.graph_text2sql_v3 import run_query_graph_v3
from api.core.graph_text2sql_v4 import run_query_graph_v4
from api.core.graph_text2sql_v4 import run_query_graph_v4
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
from api.auth.user_management import token_required, roles_allowed
from api.graph_db.factory import GraphDatabaseFactory
from api.auth.models import UserRole
from api.routes.tokens import UNAUTHORIZED_RESPONSE

graphs_router = APIRouter(tags=["Graphs & Databases"])


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
async def list_graphs(request: Request):
    graphs = await list_databases(request.state.user_id, GENERAL_PREFIX)
    return JSONResponse(content=graphs)


@graphs_router.get(
    "/{graph_id}/data",
    operation_id="database_schema",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)

@token_required
async def get_graph_data(
    request: Request, graph_id: str
):  

    try:
        schema = await get_schema(request.state.user_id, graph_id)
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


@graphs_router.post("", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
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
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        # Fallback to user-specific LLM config if not provided in request
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = user["llm_model"]
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_name(request.state.user_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query(request.state.user_id, graph_id, chat_data, db=db)
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
    "/{graph_id}/v2",
    operation_id="query_database_v2",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph_v2(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = user["llm_model"]
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_name(request.state.user_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query_graph(request.state.user_id, graph_id, chat_data, db=db)
            ):
                yield chunk
        except Exception as e: 
            import traceback
            tb = traceback.format_exc()
            logging.exception("Streaming query failed")
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": f"Internal error while processing query: {str(e)}\\n{tb}",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")


@graphs_router.post(
    "/{graph_id}/v3",
    operation_id="query_database_v3",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph_v3(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = user["llm_model"]
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_name(request.state.user_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query_graph_v3(request.state.user_id, graph_id, chat_data, db=db)
            ):
                yield chunk
        except Exception as e: 
            import traceback
            tb = traceback.format_exc()
            logging.exception("Streaming query failed")
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": f"Internal error while processing query: {str(e)}\\n{tb}",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")


@graphs_router.post(
    "/{graph_id}/v4",
    operation_id="query_database_v4",
    tags=["mcp_tool"],
    responses={401: UNAUTHORIZED_RESPONSE}
)
@token_required
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def query_graph_v4(
    request: Request, graph_id: str, chat_data: ChatRequest
):  
    try:
        user = getattr(request.state, "user", {})
        if not chat_data.custom_model and user.get("llm_model"):
            chat_data.custom_model = user["llm_model"]
            chat_data.custom_api_key = user.get("llm_api_key")
            chat_data.custom_api_base = user.get("llm_api_base")
            
        graph_name(request.state.user_id, graph_id)
        validate_and_truncate_chat(chat_data)
        validate_custom_model(getattr(chat_data, "custom_model", None))
    except InvalidArgumentError as iae:
        logging.warning("Invalid argument in query: %s", str(iae))
        return JSONResponse(content={"error": "Invalid query request"}, status_code=400)

    async def stream():
        try:
            db = await GraphDatabaseFactory.get_instance()
            async for chunk in _serialize_pipeline(
                run_query_graph_v4(request.state.user_id, graph_id, chat_data, db=db)
            ):
                yield chunk
        except Exception as e: 
            import traceback
            tb = traceback.format_exc()
            logging.exception("Streaming query failed")
            yield json.dumps({
                "type": "error",
                "final_response": True,
                "message": f"Internal error while processing query: {str(e)}\\n{tb}",
            }) + MESSAGE_DELIMITER

    return StreamingResponse(stream(), media_type="application/json")

@graphs_router.post("/{graph_id}/confirm", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
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
            confirm_data.custom_model = user["llm_model"]
            confirm_data.custom_api_key = user.get("llm_api_key")
            confirm_data.custom_api_base = user.get("llm_api_base")
            
        namespaced = graph_name(request.state.user_id, graph_id)
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
                run_confirmed(request.state.user_id, graph_id, confirm_data)
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
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def refresh_graph_schema(request: Request, graph_id: str):
    try:
        generator = await refresh_database_schema(request.state.user_id, graph_id)
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
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def execute_cypher(request: Request, graph_id: str, data: CypherRequest):
    try:
        namespaced = graph_name(request.state.user_id, graph_id)
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
async def explore_graph(request: Request, graph_id: str, limit: int = 100):
    try:
        namespaced = graph_name(request.state.user_id, graph_id)
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
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def delete_graph(request: Request, graph_id: str):

    try:
        result = await delete_database(request.state.user_id, graph_id)
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
async def get_graph_user_rules(request: Request, graph_id: str):
   
    try:
        full_graph_id = graph_name(request.state.user_id, graph_id)
        db = await GraphDatabaseFactory.get_instance()
        retriever = Retriever(graph_id=full_graph_id, db=db)
        user_rules = await retriever.get_user_rules(full_graph_id)
        logging.info("Retrieved user rules length: %d", len(user_rules) if user_rules else 0)
        return JSONResponse(content={"user_rules": user_rules})
    except GraphNotFoundError:
        return JSONResponse(content={"error": "Database not found"}, status_code=404)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error getting user rules: %s", str(e))
        return JSONResponse(content={"error": "Failed to get user rules"}, status_code=500)


@graphs_router.put("/{graph_id}/user-rules", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
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
        full_graph_id = graph_name(request.state.user_id, graph_id)
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
