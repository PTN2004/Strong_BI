"""
ORM Models cho hệ thống xác thực và phân quyền người dùng (Auth & RBAC).
Lưu trữ trên PostgreSQL, tách biệt hoàn toàn với FalkorDB dùng cho dữ liệu nghiệp vụ BI.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import JSON, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from api.database import Base


class UserRole(str, PyEnum):
    """Các vai trò phân quyền trong hệ thống."""
    ADMIN = "admin"       # Toàn quyền: quản lý users, databases, settings
    ANALYST = "analyst"   # Thực hiện truy vấn, tạo biểu đồ, lưu dashboard
    VIEWER = "viewer"     # Chỉ xem các dashboard đã được tạo sẵn

class WorkspaceRole(str, PyEnum):
    """Các vai trò phân quyền trong một Workspace."""
    OWNER = "owner"       # Chủ sở hữu workspace
    ADMIN = "admin"       # Quản lý Database connection, tạo chỉnh sửa Dashboard
    ANALYST = "analyst"   # Đặt câu hỏi AI, tạo biểu đồ
    VIEWER = "viewer"     # Chỉ có quyền xem Dashboards đã tạo


class User(Base):
    """Bảng lưu thông tin tài khoản người dùng."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_type=True),
        nullable=False,
        default=UserRole.ANALYST,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # User's specific LLM configuration
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_api_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship tới các token đăng nhập
    tokens: Mapped[list["UserToken"]] = relationship(
        "UserToken", back_populates="user", cascade="all, delete-orphan"
    )

    # Relationship tới các workspace user thuộc về
    workspace_users: Mapped[list["WorkspaceUser"]] = relationship(
        "WorkspaceUser", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


class UserToken(Base):
    """Bảng lưu các phiên đăng nhập (Session Token / API Token)."""
    __tablename__ = "user_tokens"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship ngược về User
    user: Mapped["User"] = relationship("User", back_populates="tokens")

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self) -> str:
        return f"<UserToken id={self.id[:8]}... user_id={self.user_id}>"

class Workspace(Base):
    """Bảng lưu thông tin không gian làm việc (Tenant)."""
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Business Context
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_goals: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    kpi_focus: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    workspace_users: Mapped[list["WorkspaceUser"]] = relationship(
        "WorkspaceUser", back_populates="workspace", cascade="all, delete-orphan"
    )

class WorkspaceUser(Base):
    """Bảng trung gian liên kết User và Workspace với Role cụ thể."""
    __tablename__ = "workspace_users"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(WorkspaceRole, name="workspace_role", create_type=True),
        nullable=False,
        default=WorkspaceRole.ANALYST,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="workspace_users")
    user: Mapped["User"] = relationship("User", back_populates="workspace_users")


class ChatThread(Base):
    """Log server-side mỗi lượt hỏi-đáp (thread) — phục vụ admin trace/đánh giá."""
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    graph_id: Mapped[str] = mapped_column(String(255), nullable=False)
    query: Mapped[str] = mapped_column(String(4000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="done")
    intent: Mapped[str | None] = mapped_column(String(24), nullable=True)
    playbook: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sql: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    answer: Mapped[str | None] = mapped_column(String(16000), nullable=True)
    error: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    table_data: Mapped[list | None] = mapped_column(JSON, nullable=True)
    chart_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    
    # --- Token & Cost Metrics ---
    prompt_tokens: Mapped[int | None] = mapped_column(nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    api_calls_count: Mapped[int | None] = mapped_column(nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class Dashboard(Base):
    """Bảng lưu các Dashboard tuỳ chỉnh của Workspace."""
    __tablename__ = "dashboards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    widgets: Mapped[list["DashboardWidget"]] = relationship(
        "DashboardWidget", back_populates="dashboard", cascade="all, delete-orphan"
    )

class DashboardWidget(Base):
    """Bảng lưu các Widgets (biểu đồ) bên trong một Dashboard."""
    __tablename__ = "dashboard_widgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    graph_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chart_type: Mapped[str] = mapped_column(String(50), nullable=False) # bar, line, pie, etc.
    sql_query: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    chart_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Layout configuration for react-grid-layout
    layout_x: Mapped[int] = mapped_column(default=0, nullable=False)
    layout_y: Mapped[int] = mapped_column(default=0, nullable=False)
    layout_w: Mapped[int] = mapped_column(default=6, nullable=False)
    layout_h: Mapped[int] = mapped_column(default=4, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    dashboard: Mapped["Dashboard"] = relationship("Dashboard", back_populates="widgets")
