"""Database connection routes for the text2sql API."""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth.user_management import token_required, roles_allowed, require_workspace
from api.auth.models import UserRole
from api.core.schema_loader import load_database
from api.routes.tokens import UNAUTHORIZED_RESPONSE

database_router = APIRouter(tags=["Database Connection"])

class DatabaseConnectionRequest(BaseModel):
    url: str

@database_router.post("/database", operation_id="connect_database", tags=["mcp_tool"], responses={
    401: UNAUTHORIZED_RESPONSE
})
@token_required
@require_workspace
@roles_allowed(UserRole.ADMIN, UserRole.ANALYST)
async def connect_database(request: Request, db_request: DatabaseConnectionRequest):
    generator = await load_database(db_request.url, request.state.workspace_id)
    return StreamingResponse(generator, media_type="application/json")
