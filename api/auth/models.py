"""
ORM Models cho hệ thống xác thực và phân quyền người dùng (Auth & RBAC).
Lưu trữ trên PostgreSQL, tách biệt hoàn toàn với FalkorDB dùng cho dữ liệu nghiệp vụ BI.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from api.database import Base


class UserRole(str, PyEnum):
    """Các vai trò phân quyền trong hệ thống."""
    ADMIN = "admin"       # Toàn quyền: quản lý users, databases, settings
    ANALYST = "analyst"   # Thực hiện truy vấn, tạo biểu đồ, lưu dashboard
    VIEWER = "viewer"     # Chỉ xem các dashboard đã được tạo sẵn


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
