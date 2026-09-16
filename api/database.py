"""
PostgreSQL Database engine và session factory.
Được dùng riêng cho việc quản lý xác thực và phân quyền người dùng (Auth/RBAC).
Cơ sở dữ liệu dữ liệu nghiệp vụ (BI) vẫn sử dụng FalkorDB.
"""
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)


def _get_postgres_url() -> str:
    """Xây dựng connection string PostgreSQL từ biến môi trường."""
    url = os.getenv("POSTGRES_URL")
    if url:
        return url
    
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "strongbi_auth")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "password123")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


class Base(DeclarativeBase):
    """Base class dùng chung cho tất cả các ORM model."""
    pass


# ─── Lazy singletons ───────────────────────────────────────────────────────
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            _get_postgres_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        from sqlalchemy.orm import sessionmaker
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


# Backward-compatible alias used by existing code
@property
def SessionLocal():
    return get_session_factory()


def get_db_session():
    """
    Dependency FastAPI: Tạo một DB Session cho mỗi request.
    Session sẽ tự động đóng lại sau khi request hoàn tất.
    """
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Tự động tạo tất cả các bảng được định nghĩa trong ORM model.
    Gọi hàm này khi server khởi động.
    """
    from api.auth.models import User, UserToken, Workspace, WorkspaceUser, Dashboard, DashboardWidget  # noqa: F401
    try:
        engine = _get_engine()
        Base.metadata.create_all(bind=engine)
        
        # Add new LLM configuration columns to existing users table
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(50);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_api_key VARCHAR(255);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_api_base VARCHAR(255);"))
            
            # Add new token & cost columns to chat_threads table
            conn.execute(text("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER;"))
            conn.execute(text("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS completion_tokens INTEGER;"))
            conn.execute(text("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS total_tokens INTEGER;"))
            conn.execute(text("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS cost_usd FLOAT;"))
            conn.execute(text("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS api_calls_count INTEGER;"))
            conn.execute(text("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS engine_version VARCHAR(16);"))
            conn.execute(text("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS workspace_id UUID;"))
            
            # Add new business context columns to workspaces table
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS industry VARCHAR(100);"))
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS business_goals VARCHAR(1000);"))
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS kpi_focus VARCHAR(1000);"))
            
        logger.info("PostgreSQL tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL tables: {e}")
        raise
