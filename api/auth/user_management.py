"""
Quản lý người dùng thông qua PostgreSQL (Auth & RBAC).
Module này thay thế hoàn toàn logic Auth cũ (FalkorDB) bằng SQLAlchemy + PostgreSQL.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Optional, Dict, Any, Callable

from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from api.auth.models import User, UserToken, UserRole

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("FASTAPI_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("FASTAPI_SECRET_KEY not set, using generated key. Set this in production!")

# Thời gian hiệu lực của token đăng nhập: 14 ngày
TOKEN_EXPIRY_DAYS = 14


# ─────────────────────────────────────────────────────────────────────
# Helpers: Mật khẩu
# ─────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng PBKDF2-HMAC-SHA256 với salt ngẫu nhiên."""
    salt = os.urandom(32)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return (salt + password_hash).hex()


def verify_password(password: str, stored_password_hex: str) -> bool:
    """Xác minh mật khẩu so với hash đã lưu."""
    try:
        stored_bytes = bytes.fromhex(stored_password_hex)
        salt = stored_bytes[:32]
        stored_hash = stored_bytes[32:]
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(computed, stored_hash)
    except (ValueError, TypeError):
        return False


def _validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


# ─────────────────────────────────────────────────────────────────────
# CRUD: Đăng ký (Register)
# ─────────────────────────────────────────────────────────────────────

def register_user(
    db: Session,
    email: str,
    password: str,
    first_name: str,
    last_name: str = "",
    role: UserRole = UserRole.ANALYST,
) -> Dict[str, Any]:
    """
    Tạo tài khoản người dùng mới trong PostgreSQL.
    Trả về thông tin user và token đã tạo.
    Raises ValueError nếu email đã tồn tại hoặc dữ liệu không hợp lệ.
    """
    email = email.strip().lower()

    if not _validate_email(email):
        raise ValueError("Invalid email format.")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    # Kiểm tra email đã tồn tại chưa
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ValueError("Email already registered.")

    # Tạo user mới
    new_user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role=role,
    )
    db.add(new_user)
    db.flush()  # flush để lấy id trước khi commit

    # Tạo token đăng nhập ngay sau khi đăng ký
    token = _create_token(db, new_user.id)

    db.commit()
    db.refresh(new_user)

    logger.info("New user registered: %s (role=%s)", email, role.value)
    return {
        "user": new_user,
        "token": token.id,
        "new_user": True,
    }


# ─────────────────────────────────────────────────────────────────────
# CRUD: Đăng nhập (Login)
# ─────────────────────────────────────────────────────────────────────

def authenticate_user(db: Session, email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Xác thực email/password và tạo token mới nếu hợp lệ.
    Trả về dict chứa user và token, hoặc None nếu thất bại.
    """
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email, User.is_active == True).first()

    if not user or not verify_password(password, user.password_hash):
        logger.warning("Failed login attempt for email: %s", email)
        return None

    # Cập nhật thời gian đăng nhập
    user.updated_at = datetime.now(timezone.utc)

    # Tạo token mới
    token = _create_token(db, user.id)
    db.commit()
    db.refresh(user)

    logger.info("User authenticated: %s", email)
    return {
        "user": user,
        "token": token.id,
    }


# ─────────────────────────────────────────────────────────────────────
# CRUD: Xác minh Token (Session check)
# ─────────────────────────────────────────────────────────────────────

def get_user_by_token(db: Session, token_id: str) -> Optional[User]:
    """
    Tìm user dựa trên token đăng nhập.
    Trả về User nếu token còn hiệu lực, None nếu hết hạn hoặc không tồn tại.
    """
    token = db.query(UserToken).filter(UserToken.id == token_id).first()
    if not token:
        return None

    if token.is_expired():
        db.delete(token)
        db.commit()
        return None

    user = db.query(User).filter(User.id == token.user_id, User.is_active == True).first()
    return user


# ─────────────────────────────────────────────────────────────────────
# CRUD: Đăng xuất (Logout)
# ─────────────────────────────────────────────────────────────────────

def delete_token(db: Session, token_id: str) -> None:
    """Xóa token đăng nhập (đăng xuất)."""
    token = db.query(UserToken).filter(UserToken.id == token_id).first()
    if token:
        db.delete(token)
        db.commit()
        logger.info("Token deleted (logout): %s...", token_id[:8])


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _create_token(db: Session, user_id) -> UserToken:
    """Tạo một UserToken mới và thêm vào session."""
    token = UserToken(
        id=secrets.token_urlsafe(32),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
    )
    db.add(token)
    return token


# ─────────────────────────────────────────────────────────────────────
# Backward-compatible decorator: @token_required
# Dùng bởi các routes cũ (graphs, database, tokens, settings)
# ─────────────────────────────────────────────────────────────────────

def token_required(func: Callable) -> Callable:
    """
    Decorator kiểm tra xác thực thông qua cookie 'api_token' trong PostgreSQL.
    Nếu token hợp lệ, inject 'user' vào kwargs của route handler.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Lấy Request từ args hoặc kwargs
        request: Optional[Request] = kwargs.get("request")
        if request is None:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

        if request is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        api_token = request.cookies.get("api_token")
        if not api_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authenticated",
            )

        from api.database import get_session_factory
        db = get_session_factory()()
        try:
            user = get_user_by_token(db, api_token)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid or expired token",
                )
            user_dict = {
                "id": str(user.id),
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "role": user.role.value,
                "llm_provider": user.llm_provider,
                "llm_model": user.llm_model,
                "llm_api_key": user.llm_api_key,
                "llm_api_base": user.llm_api_base,
            }
            request.state.user = user_dict
            request.state.user_id = str(user.id)
            
            import inspect
            sig = inspect.signature(func)
            if "user" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs["user"] = user_dict
        finally:
            db.close()

        return await func(*args, **kwargs)
    return wrapper


def roles_allowed(*roles: UserRole) -> Callable:
    """
    Decorator kiểm tra vai trò người dùng sau khi @token_required đã được chạy.
    Yêu cầu request phải có request.state.user được inject từ @token_required.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request is None or not hasattr(request.state, "user"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            
            user_role = request.state.user.get("role")
            allowed_role_values = [r.value for r in roles]
            if user_role not in allowed_role_values:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied: Insufficient privileges",
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────
# Admin Panel Helpers: List & Update users
# ─────────────────────────────────────────────────────────────────────

def list_all_users(db: Session) -> list[User]:
    """Trả về danh sách tất cả người dùng trong PostgreSQL."""
    return db.query(User).order_by(User.created_at.desc()).all()


def update_user_role_and_status(
    db: Session,
    target_user_id: str,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
) -> Optional[User]:
    """Cập nhật vai trò và trạng thái của một người dùng."""
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        return None

    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
        
    db.commit()
    db.refresh(user)
    return user


def create_user_by_admin(
    db: Session,
    email: str,
    password: str,
    first_name: str,
    last_name: str = "",
    role: UserRole = UserRole.ANALYST,
) -> User:
    """
    Admin tạo tài khoản mới cho người dùng khác.
    Không tạo token đăng nhập (user tự login sau).
    Raises ValueError nếu dữ liệu không hợp lệ.
    """
    email = email.strip().lower()

    if not _validate_email(email):
        raise ValueError("Invalid email format.")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ValueError("Email already registered.")

    new_user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role=role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info("Admin created user: %s (role=%s)", email, role.value)
    return new_user


def delete_user_by_admin(db: Session, target_user_id: str) -> bool:
    """
    Admin xóa tài khoản người dùng khỏi hệ thống.
    Trả về True nếu xóa thành công, False nếu không tìm thấy user.
    """
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        return False

    db.delete(user)
    db.commit()
    logger.info("Admin deleted user: %s", target_user_id)
    return True
