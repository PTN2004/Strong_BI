"""API xem lại conversation — admin trace mọi account, user chỉ xem của mình."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.auth.models import ChatThread, UserRole, WorkspaceRole
from api.auth.user_management import token_required, require_workspace
from api.database import get_session_factory

UNAUTHORIZED_RESPONSE = {"description": "Unauthorized"}

conversations_router = APIRouter(tags=["Conversations"])


def _is_admin(request: Request) -> bool:
    return (request.state.user.get("role") or "").lower() == UserRole.ADMIN.value

def _is_workspace_admin(request: Request) -> bool:
    return getattr(request.state, "workspace_role", "") in (WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value)


def _summary(t: ChatThread) -> dict:
    return {
        "id": t.id, "user_email": t.user_email, "graph_id": t.graph_id,
        "query": t.query, "status": t.status, "intent": t.intent,
        "playbook": t.playbook, "duration_ms": t.duration_ms,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "has_error": bool(t.error),
        "total_tokens": t.total_tokens,
        "cost_usd": t.cost_usd,
        "api_calls_count": t.api_calls_count,
    }


@conversations_router.get("/metrics/total", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def get_total_metrics(request: Request) -> JSONResponse:
    """Return total metrics for the workspace."""
    db = get_session_factory()()
    try:
        from sqlalchemy import func
        q = db.query(
            func.sum(ChatThread.cost_usd).label("total_cost"),
            func.sum(ChatThread.total_tokens).label("total_tokens"),
            func.sum(ChatThread.api_calls_count).label("total_api_calls"),
            func.count(ChatThread.id).label("total_chats")
        )
        if not _is_admin(request):
            q = q.filter(ChatThread.workspace_id == request.state.workspace_id)
            
        result = q.first()
        
        return JSONResponse({
            "total_cost_usd": float(result.total_cost or 0),
            "total_tokens": int(result.total_tokens or 0),
            "total_api_calls": int(result.total_api_calls or 0),
            "total_chats": int(result.total_chats or 0)
        })
    finally:
        db.close()


@conversations_router.get("", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def list_conversations(request: Request, user_email: str | None = None,
                             limit: int = 50, offset: int = 0) -> JSONResponse:
    """ADMIN: mọi account; workspace admin: toàn bộ workspace; user thường: chỉ của mình trong workspace."""
    limit = max(1, min(limit, 200))
    db = get_session_factory()()
    try:
        q = db.query(ChatThread)
        if _is_admin(request):
            if user_email:
                q = q.filter(ChatThread.user_email == user_email.strip().lower())
        else:
            q = q.filter(ChatThread.workspace_id == request.state.workspace_id)
            if not _is_workspace_admin(request):
                q = q.filter(ChatThread.user_id == request.state.user_id)
                
        rows = (q.order_by(ChatThread.created_at.desc())
                 .offset(max(0, offset)).limit(limit).all())
        return JSONResponse({"conversations": [_summary(t) for t in rows]})
    finally:
        db.close()


@conversations_router.get("/{thread_id}", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def get_conversation(request: Request, thread_id: str) -> JSONResponse:
    """Chi tiết FULL trace (steps/SQL/data/chart/error) — chủ thread, workspace admin hoặc ADMIN."""
    db = get_session_factory()()
    try:
        t = db.get(ChatThread, thread_id)
        if t is None:
            return JSONResponse({"error": "Không tìm thấy conversation"}, status_code=404)
            
        is_owner = str(t.user_id) == str(request.state.user_id)
        is_ws_admin = _is_workspace_admin(request) and str(t.workspace_id) == str(request.state.workspace_id)
        
        if not (_is_admin(request) or is_owner or is_ws_admin):
            return JSONResponse({"error": "Không có quyền xem conversation này"}, status_code=403)
        detail = _summary(t)
        detail.update({"answer": t.answer, "error": t.error, "steps": t.steps})
        # Non-admin (chủ thread) chỉ thấy thêm phần nằm trong ui_permissions của họ
        if _is_admin(request):
            allowed = {"sql", "data", "chart"}
        else:
            tabs = set((request.state.user.get("ui_permissions") or {}).get("result_tabs", []))
            allowed = tabs
        detail["sql"] = t.sql if "sql" in allowed else None
        detail["table_data"] = t.table_data if "data" in allowed else None
        detail["chart_config"] = t.chart_config if "chart" in allowed else None
        return JSONResponse(detail)
    finally:
        db.close()
