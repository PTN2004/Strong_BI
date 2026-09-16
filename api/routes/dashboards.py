from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from api.auth.models import Dashboard, DashboardWidget, UserRole, WorkspaceRole
from api.auth.user_management import token_required, require_workspace
from api.database import get_session_factory
from sqlalchemy.orm import Session

UNAUTHORIZED_RESPONSE = {"description": "Unauthorized"}

dashboards_router = APIRouter(tags=["Dashboards"])

class WidgetCreate(BaseModel):
    title: str
    graph_id: Optional[str] = None
    chart_type: str
    sql_query: Optional[str] = None
    chart_config: Optional[Dict[str, Any]] = None
    layout_x: int = 0
    layout_y: int = 0
    layout_w: int = 6
    layout_h: int = 4

class WidgetUpdate(BaseModel):
    title: Optional[str] = None
    layout_x: Optional[int] = None
    layout_y: Optional[int] = None
    layout_w: Optional[int] = None
    layout_h: Optional[int] = None

class DashboardCreate(BaseModel):
    name: str
    description: Optional[str] = None
    widgets: Optional[List[WidgetCreate]] = []

def _can_edit_dashboard(request: Request) -> bool:
    role = getattr(request.state, "workspace_role", "")
    return role in (WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value, WorkspaceRole.ANALYST.value)

@dashboards_router.get("", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def list_dashboards(request: Request) -> JSONResponse:
    db = get_session_factory()()
    try:
        dashboards = db.query(Dashboard).filter(Dashboard.workspace_id == request.state.workspace_id).order_by(Dashboard.created_at.desc()).all()
        return JSONResponse({
            "dashboards": [
                {
                    "id": str(d.id),
                    "name": d.name,
                    "description": d.description,
                    "created_at": d.created_at.isoformat() if d.created_at else None
                } for d in dashboards
            ]
        })
    finally:
        db.close()

@dashboards_router.post("", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def create_dashboard(request: Request, data: DashboardCreate) -> JSONResponse:
    if not _can_edit_dashboard(request):
        return JSONResponse({"error": "Bạn không có quyền tạo Dashboard"}, status_code=403)
        
    db = get_session_factory()()
    try:
        new_dashboard = Dashboard(
            workspace_id=request.state.workspace_id,
            user_id=request.state.user_id,
            name=data.name,
            description=data.description
        )
        db.add(new_dashboard)
        db.commit()
        
        for w in (data.widgets or []):
            widget = DashboardWidget(
                dashboard_id=new_dashboard.id,
                title=w.title,
                graph_id=w.graph_id,
                chart_type=w.chart_type,
                sql_query=w.sql_query,
                chart_config=w.chart_config,
                layout_x=w.layout_x,
                layout_y=w.layout_y,
                layout_w=w.layout_w,
                layout_h=w.layout_h
            )
            db.add(widget)
        
        db.commit()
        return JSONResponse({"id": str(new_dashboard.id), "name": new_dashboard.name, "message": "Tạo dashboard thành công"})
    finally:
        db.close()

@dashboards_router.get("/{dashboard_id}", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def get_dashboard(request: Request, dashboard_id: str) -> JSONResponse:
    db = get_session_factory()()
    try:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.workspace_id == request.state.workspace_id
        ).first()
        
        if not dashboard:
            return JSONResponse({"error": "Không tìm thấy dashboard"}, status_code=404)
            
        widgets = []
        for w in dashboard.widgets:
            widgets.append({
                "id": str(w.id),
                "title": w.title,
                "graph_id": w.graph_id,
                "chart_type": w.chart_type,
                "sql_query": w.sql_query,
                "chart_config": w.chart_config,
                "layout": {
                    "x": w.layout_x,
                    "y": w.layout_y,
                    "w": w.layout_w,
                    "h": w.layout_h
                }
            })
            
        return JSONResponse({
            "id": str(dashboard.id),
            "name": dashboard.name,
            "description": dashboard.description,
            "widgets": widgets
        })
    finally:
        db.close()

@dashboards_router.delete("/{dashboard_id}", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def delete_dashboard(request: Request, dashboard_id: str) -> JSONResponse:
    if not _can_edit_dashboard(request):
        return JSONResponse({"error": "Bạn không có quyền xóa Dashboard"}, status_code=403)
        
    db = get_session_factory()()
    try:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.workspace_id == request.state.workspace_id
        ).first()
        
        if not dashboard:
            return JSONResponse({"error": "Không tìm thấy dashboard"}, status_code=404)
            
        db.delete(dashboard)
        db.commit()
        return JSONResponse({"message": "Đã xóa dashboard"})
    finally:
        db.close()

@dashboards_router.post("/{dashboard_id}/widgets", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def add_widget(request: Request, dashboard_id: str, data: WidgetCreate) -> JSONResponse:
    if not _can_edit_dashboard(request):
        return JSONResponse({"error": "Bạn không có quyền chỉnh sửa Dashboard"}, status_code=403)
        
    db = get_session_factory()()
    try:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.workspace_id == request.state.workspace_id
        ).first()
        
        if not dashboard:
            return JSONResponse({"error": "Không tìm thấy dashboard"}, status_code=404)
            
        widget = DashboardWidget(
            dashboard_id=dashboard.id,
            title=data.title,
            graph_id=data.graph_id,
            chart_type=data.chart_type,
            sql_query=data.sql_query,
            chart_config=data.chart_config,
            layout_x=data.layout_x,
            layout_y=data.layout_y,
            layout_w=data.layout_w,
            layout_h=data.layout_h
        )
        db.add(widget)
        db.commit()
        return JSONResponse({"id": str(widget.id), "message": "Đã thêm widget thành công"})
    finally:
        db.close()

@dashboards_router.put("/{dashboard_id}/widgets/{widget_id}", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def update_widget(request: Request, dashboard_id: str, widget_id: str, data: WidgetUpdate) -> JSONResponse:
    if not _can_edit_dashboard(request):
        return JSONResponse({"error": "Bạn không có quyền chỉnh sửa Dashboard"}, status_code=403)
        
    db = get_session_factory()()
    try:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.workspace_id == request.state.workspace_id
        ).first()
        
        if not dashboard:
            return JSONResponse({"error": "Không tìm thấy dashboard"}, status_code=404)
            
        widget = db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id,
            DashboardWidget.dashboard_id == dashboard.id
        ).first()
        
        if not widget:
            return JSONResponse({"error": "Không tìm thấy widget"}, status_code=404)
            
        if data.title is not None:
            widget.title = data.title
        if data.layout_x is not None:
            widget.layout_x = data.layout_x
        if data.layout_y is not None:
            widget.layout_y = data.layout_y
        if data.layout_w is not None:
            widget.layout_w = data.layout_w
        if data.layout_h is not None:
            widget.layout_h = data.layout_h
            
        db.commit()
        return JSONResponse({"message": "Đã cập nhật widget"})
    finally:
        db.close()

@dashboards_router.delete("/{dashboard_id}/widgets/{widget_id}", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
@require_workspace
async def delete_widget(request: Request, dashboard_id: str, widget_id: str) -> JSONResponse:
    if not _can_edit_dashboard(request):
        return JSONResponse({"error": "Bạn không có quyền chỉnh sửa Dashboard"}, status_code=403)
        
    db = get_session_factory()()
    try:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.workspace_id == request.state.workspace_id
        ).first()
        
        if not dashboard:
            return JSONResponse({"error": "Không tìm thấy dashboard"}, status_code=404)
            
        widget = db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id,
            DashboardWidget.dashboard_id == dashboard.id
        ).first()
        
        if not widget:
            return JSONResponse({"error": "Không tìm thấy widget"}, status_code=404)
            
        db.delete(widget)
        db.commit()
        return JSONResponse({"message": "Đã xóa widget"})
    finally:
        db.close()
