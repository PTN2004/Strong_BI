import hashlib
import hmac
import logging
import os
import re
import secrets
from typing import Optional, List

from pathlib import Path
from urllib.parse import urljoin

from authlib.integrations.starlette_client import OAuth

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache, select_autoescape
from starlette.config import Config
from pydantic import BaseModel

from api.database import get_db_session
from api.auth.user_management import (
    register_user, authenticate_user, get_user_by_token, delete_token
)
from api.auth.models import UserRole

# Import GENERAL_PREFIX from graphs route
GENERAL_PREFIX = os.getenv("GENERAL_PREFIX")

# Router
auth_router = APIRouter(tags=["Authentication"])
TEMPLATES_DIR = str(
    (Path(__file__).resolve().parents[1] / "../app/templates").resolve())

TEMPLATES_CACHE_DIR = "/tmp/jinja_cache"
os.makedirs(TEMPLATES_CACHE_DIR, exist_ok=True)  # ✅ ensures the folder exists

templates = Jinja2Templates(
    env=Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        bytecode_cache=FileSystemBytecodeCache(
            directory=TEMPLATES_CACHE_DIR,
            pattern="%s.cache"
        ),
        auto_reload=True,
        autoescape=select_autoescape(['html', 'xml', 'j2'])
    )
)

templates.env.globals["google_tag_manager_id"] = os.getenv(
    "GOOGLE_TAG_MANAGER_ID")

GOOGLE_AUTH = bool(os.getenv("GOOGLE_CLIENT_ID")
                   and os.getenv("GOOGLE_CLIENT_SECRET"))
GITHUB_AUTH = bool(os.getenv("GITHUB_CLIENT_ID")
                   and os.getenv("GITHUB_CLIENT_SECRET"))
EMAIL_AUTH = bool(os.getenv("EMAIL_AUTH_ENABLED", "").lower()
                  in ["true", "1", "yes", "on"])


def _is_email_auth_enabled() -> bool:
    return EMAIL_AUTH or not (GOOGLE_AUTH or GITHUB_AUTH)


def _is_google_auth_enabled() -> bool:
    return GOOGLE_AUTH


def _is_github_auth_enabled() -> bool:
    return GITHUB_AUTH


def _get_auth_config() -> dict:
    return {
        "email_auth_enabled": _is_email_auth_enabled(),
        "google_auth_enabled": _is_google_auth_enabled(),
        "github_auth_enabled": _is_github_auth_enabled(),
    }


class EmailLoginRequest(BaseModel):
    email: str
    password: str


class EmailSignupRequest(BaseModel):
    firstName: str
    lastName: str
    email: str
    password: str


def _is_request_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        return forwarded_proto == "https"
    return request.url.scheme == "https"


# ─────────────────────────────────────────────────────────────────────
# PostgreSQL-backed Email Auth endpoints
# ─────────────────────────────────────────────────────────────────────

@auth_router.post("/signup/email")
def email_signup_pg(request: Request, signup_data: EmailSignupRequest) -> JSONResponse:
    """Đăng ký tài khoản mới, lưu trên PostgreSQL."""
    db = next(get_db_session())
    try:
        result = register_user(
            db=db,
            email=signup_data.email,
            password=signup_data.password,
            first_name=signup_data.firstName,
            last_name=signup_data.lastName,
            role=UserRole.ANALYST,
        )
        response = JSONResponse({"success": True}, status_code=201)
        response.set_cookie(
            key="api_token",
            value=result["token"],
            httponly=True,
            secure=_is_request_secure(request),
            samesite="lax",
            max_age=14 * 24 * 3600,
        )
        return response
    except ValueError as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logging.error("Signup error: %s", e)
        return JSONResponse(
            {"success": False, "error": "Registration failed"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        db.close()


@auth_router.post("/login/email")
def email_login_pg(request: Request, login_data: EmailLoginRequest) -> JSONResponse:
    """Đăng nhập bằng email/password, xác thực qua PostgreSQL."""
    db = next(get_db_session())
    try:
        result = authenticate_user(db, login_data.email, login_data.password)
        if not result:
            return JSONResponse(
                {"success": False, "error": "Invalid email or password"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        response = JSONResponse({"success": True}, status_code=200)
        response.set_cookie(
            key="api_token",
            value=result["token"],
            httponly=True,
            secure=_is_request_secure(request),
            samesite="lax",
            max_age=14 * 24 * 3600,
        )
        return response
    except Exception as e:
        logging.error("Login error: %s", e)
        return JSONResponse(
            {"success": False, "error": "Login failed"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        db.close()


def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    password_hash = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, 100000)
    return (salt + password_hash).hex()


def _verify_password(password: str, stored_password_hex: str) -> bool:
    try:
        stored_password = bytes.fromhex(stored_password_hex)
        salt = stored_password[:32]
        stored_hash = stored_password[32:]

        password_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt, 100000)

        return hmac.compare_digest(password_hash, stored_hash)
    except (ValueError, TypeError):
        return False


def _sanitize_for_log(value: str) -> str:
    if not isinstance(value, str):
        return str(value)
    return value.replace('\r\n', '').replace('\n', '').replace('\r', '')


def _validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


async def _set_mail_hash(email: str, password_hash: str) -> bool:
    """Set email hash for the user in the database."""
    try:
        db = await get_default_db()
        db.select_graph("Organizations")
        # Sanitize inputs for logging
        safe_email = _sanitize_for_log(email)

        # Create new email identity and user
        create_query = """
        MERGE (i:Identity {
            provider_user_id: $email,
            email: $email
        })
        SET i.password_hash = $password_hash
        RETURN i
        """

        result = await db.query(create_query, {
            "email": email,
            "password_hash": password_hash,
        })

        if result.result_set:
            return True
        else:
            logging.error("Failed to set email hash for user: %s", safe_email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    except Exception as e:
        logging.error(
            "Error setting email hash for user %s: %s", safe_email, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def _is_request_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        return forwarded_proto == "https"

    return request.url.scheme == "https"


async def _authenticate_email_user(email: str, password: str):
    """Authenticate an email user."""
    try:
        db = await get_default_db()
        db.select_graph("Organizations")
        # Find user by email
        query = """
        MATCH (i:Identity {provider: 'email', email: $email})-[:AUTHENTICATES]->(u:User)
        RETURN i, u
        """

        result = await db.query(query, {"email": email})

        if not result.result_set:
            return False, "Invalid email or password"

        row = result.result_set[0]
        identity = row.get("identity", {})
        user = row.get("user", {})

        # Verify password - access Node properties correctly
        stored_password_hash = identity.properties.get('password_hash')
        if not stored_password_hash or not _verify_password(password, stored_password_hash):
            return False, "Invalid email or password"

        # Update last login
        update_query = """
        MATCH (i:Identity {provider: 'email', email: $email})
        SET i.last_login = timestamp()
        """
        await db.query(update_query, {"email": email})

        logging.info("EMAIL USER AUTHENTICATED: email=%r",
                     _sanitize_for_log(email))
        return True, {"identity": identity, "user": user}

    except Exception as e:
        logging.error("Error authenticating email user: %s", e)
        return False, "Internal error"


@auth_router.post("/signup/email")
async def email_signup(request: Request, signup_data: EmailSignupRequest) -> JSONResponse:
    try:
        if not _is_email_auth_enabled():
            return JSONResponse(
                {"success": False, "error": "Email authentication is not enabled"},
                status_code=status.HTTP_403_FORBIDDEN
            )

        if not all([signup_data.firstName, signup_data.lastName,
                    signup_data.email, signup_data.password]):
            return JSONResponse(
                {"success": False, "error": "All fields are required"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        first_name = signup_data.firstName.strip()
        last_name = signup_data.lastName.strip()
        email = signup_data.email.strip().lower()
        password = signup_data.password

        if not _validate_email(email):
            return JSONResponse(
                {"success": False, "error": "Invalid email format"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if len(password) < 8:
            return JSONResponse(
                {"success": False, "error": "Password must be at least 8 characters long"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        api_token = secrets.token_urlsafe(32)
        success, user_info = await ensure_user_in_organizations(email, email,
                                                                f"{first_name} {last_name}", "email", api_token)

        if success and user_info and user_info["new_identity"]:
            logging.info("New user created: %s", _sanitize_for_log(email))

            # Hash password
            password_hash = _hash_password(password)

            # Set email hash
            await _set_mail_hash(email, password_hash)

        else:
            logging.info("User already exists: %s", _sanitize_for_log(email))

        logging.info("User registration successful: %s",
                     _sanitize_for_log(email))

        response = JSONResponse({
            "success": True,
        }, status_code=201)
        response.set_cookie(
            key="api_token",
            value=api_token,
            httponly=True,
            secure=_is_request_secure(request)
        )
        return response

    except Exception as e:
        logging.error("Signup error: %s", e)
        return JSONResponse(
            {"success": False, "error": "Registration failed"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@auth_router.post("/login/email")
async def email_login(request: Request, login_data: EmailLoginRequest) -> JSONResponse:
    """Handle email/password user login."""
    try:
        # Check if email authentication is enabled
        if not _is_email_auth_enabled():
            return JSONResponse(
                {"success": False, "error": "Email authentication is not enabled"},
                status_code=status.HTTP_403_FORBIDDEN
            )

        # Validate required fields
        if not login_data.email or not login_data.password:
            return JSONResponse(
                {"success": False, "error": "Email and password are required"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        email = login_data.email.strip().lower()
        password = login_data.password

        # Validate email format
        if not _validate_email(email):
            return JSONResponse(
                {"success": False, "error": "Invalid email format"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user
        success, result = await _authenticate_email_user(email, password)

        if not success:
            return JSONResponse(
                {"success": False, "error": result},
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Set session data - result is a dict when success is True
        if isinstance(result, dict):
            identity_node = result.get("identity")

            identity_props = (
                identity_node.properties
                if identity_node and hasattr(identity_node, "properties")
                else {}
            )

            user_data = {
                'id': identity_props.get("provider_user_id", email),
                'email': identity_props.get('email', email),
                'name': identity_props.get('name', ''),
                'picture': identity_props.get('picture', ''),
            }

            # Call the registered Google callback handler if it exists to store user data.
            handler = getattr(request.app.state, "callback_handler", None)
            if handler:
                api_token = secrets.token_urlsafe(
                    32)  # ~43 chars, hard to guess

                # Call the registered handler (await if async)
                await handler('email', user_data, api_token)
                response = JSONResponse({"success": True}, status_code=200)

                response.set_cookie(
                    key="api_token",
                    value=api_token,
                    httponly=True,
                    secure=_is_request_secure(request)
                )
                return response

        return JSONResponse(
            {"success": False, "error": "Authentication failed"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logging.error("Login error: %s", e)
        return JSONResponse(
            {"success": False, "error": "Login failed"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ---- Helpers ----


def _get_provider_client(request: Request, provider: str):
    """Get an OAuth provider client from app.state.oauth"""
    oauth = getattr(request.app.state, "oauth", None)
    if not oauth:
        raise HTTPException(status_code=500, detail="OAuth not configured")

    client = getattr(oauth, provider, None)
    if not client:
        raise HTTPException(
            status_code=500, detail=f"OAuth provider {provider} not configured")
    return client


def _build_callback_url(request: Request, path: str) -> str:
    """Build absolute callback URL, honoring OAUTH_BASE_URL if provided."""
    base_override = os.getenv("OAUTH_BASE_URL")
    base = base_override if base_override else str(request.base_url)
    if not base.endswith("/"):
        base += "/"
    return urljoin(base, path.lstrip("/"))

# ---- Routes ----


@auth_router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> HTMLResponse:
    """
    Serve the React SPA (Single Page Application).
    The React app handles authentication state via /auth-status endpoint.
    """
    from fastapi.responses import FileResponse

    # Serve the React build's index.html
    dist_path = Path(__file__).resolve().parents[1] / "../app/dist"
    index_path = dist_path / "index.html"

    if not index_path.exists():
        return HTMLResponse(
            content="""
            <html>
                <head><title>QueryWeaver - Build Required</title></head>
                <body style="font-family: system-ui; padding: 2rem; max-width: 800px; margin: 0 auto;">
                    <h1>🛠️ Frontend Not Built</h1>
                    <p>Please build the React frontend first:</p>
                    <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px;">cd app && npm run build</pre>
                    <p>Or run in development mode (recommended for development):</p>
                    <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px;">cd app && npm run dev</pre>
                    <p><small>The dev server will run on <a href="http://localhost:8080">http://localhost:8080</a> with hot reload.</small></p>
                </body>
            </html>
            """,
            status_code=503
        )

    return FileResponse(index_path)


@auth_router.get("/login/google", name="google.login", response_class=RedirectResponse)
async def login_google(request: Request) -> RedirectResponse:
    """Initiate Google OAuth login flow.

    Args:
        request (Request): The incoming request.

    Returns:
        RedirectResponse: The redirect response to the Google OAuth endpoint.
    """

    # Check if Google auth is enabled
    if not _is_google_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google authentication is not configured"
        )

    google = _get_provider_client(request, "google")
    redirect_uri = _build_callback_url(request, "login/google/authorized")

    # Helpful hint if localhost vs 127.0.0.1 mismatch is likely
    if not os.getenv("OAUTH_BASE_URL") and "127.0.0.1" in str(request.base_url):
        logging.warning(
            "OAUTH_BASE_URL not set and base URL is 127.0.0.1; "
            "if your Google OAuth app uses 'http://localhost:5000', "
            "set OAUTH_BASE_URL=http://localhost:5000 to avoid redirect_uri mismatch."
        )

    return await google.authorize_redirect(request, redirect_uri)


@auth_router.get("/login/google/authorized", response_class=RedirectResponse)
async def google_authorized(request: Request) -> RedirectResponse:
    """
    Handle Google OAuth callback and user authorization.

    Args:
        request (Request): The incoming request.

    Returns:
        RedirectResponse: The redirect response after handling the callback.
    """
    # Check if Google auth is enabled
    if not _is_google_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google authentication is not configured"
        )

    try:
        google = _get_provider_client(request, "google")
        token = await google.authorize_access_token(request)
        resp = await google.get("userinfo", token=token)
        if resp.status_code != 200:
            logging.warning("Failed to retrieve user info from Google")
            raise HTTPException(
                status_code=400, detail="Failed to get user info from Google")

        user_info = resp.json()

        if user_info:
            user_data = {
                'id': user_info.get('id') or user_info.get('sub'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
            }

            # Call the registered Google callback handler if it exists to store user data.
            handler = getattr(request.app.state, "callback_handler", None)
            if handler:
                api_token = secrets.token_urlsafe(
                    32)  # ~43 chars, hard to guess

                # Call the registered handler (await if async)
                await handler('google', user_data, api_token)

                redirect = RedirectResponse(url="/", status_code=302)
                redirect.set_cookie(
                    key="api_token",
                    value=api_token,
                    httponly=True,
                    secure=True
                )

                return redirect

            # Handler not set - log and raise error to prevent silent failure
            logging.error(
                "Google OAuth callback handler not registered in app state")
            raise HTTPException(
                status_code=500, detail="Authentication handler not configured")

        # If we reach here, user_info was falsy
        logging.warning("No user info received from Google OAuth")
        raise HTTPException(
            status_code=400, detail="Failed to get user info from Google")

    except Exception as e:
        logging.error("Google OAuth authentication failed: %s",
                      str(e))  # nosemgrep
        raise HTTPException(
            status_code=400, detail="Authentication failed") from e


@auth_router.get("/login/google/callback", response_class=RedirectResponse)
async def google_callback_compat(request: Request) -> RedirectResponse:
    """Handle Google OAuth callback redirect for compatibility."""
    qs = f"?{request.url.query}" if request.url.query else ""
    redirect = f"/login/google/authorized{qs}"
    return RedirectResponse(url=redirect, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@auth_router.get("/login/github",  name="github.login", response_class=RedirectResponse)
async def login_github(request: Request) -> RedirectResponse:
    """Handle GitHub OAuth login redirect."""
    # Check if GitHub auth is enabled
    if not _is_github_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub authentication is not configured"
        )

    github = _get_provider_client(request, "github")
    redirect_uri = _build_callback_url(request, "login/github/authorized")

    # Helpful hint if localhost vs 127.0.0.1 mismatch is likely
    if not os.getenv("OAUTH_BASE_URL") and "127.0.0.1" in str(request.base_url):
        logging.warning(
            "OAUTH_BASE_URL not set and base URL is 127.0.0.1; "
            "if your GitHub OAuth app uses 'http://localhost:5000', "
            "set OAUTH_BASE_URL=http://localhost:5000 to avoid redirect_uri mismatch."
        )

    return await github.authorize_redirect(request, redirect_uri)


@auth_router.get("/login/github/authorized", response_class=RedirectResponse)
async def github_authorized(request: Request) -> RedirectResponse:
    """Handle GitHub OAuth authorization callback."""
    # Check if GitHub auth is enabled
    if not _is_github_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub authentication is not configured"
        )
    try:
        github = _get_provider_client(request, "github")
        token = await github.authorize_access_token(request)

        # Fetch GitHub user info
        resp = await github.get("user", token=token)
        if resp.status_code != 200:
            logging.error("Failed to fetch GitHub user info: %s",
                          resp.text)  # nosemgrep
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

        user_info = resp.json()

        # Get user email if not public
        email = user_info.get("email")
        if not email:
            # Try to get primary email from emails endpoint
            email_resp = await github.get("user/emails", token=token)
            if email_resp.status_code == 200:
                emails = email_resp.json()
                for email_obj in emails:
                    if email_obj.get("primary"):
                        email = email_obj.get("email")
                        break

        if user_info:
            user_data = {
                'id': user_info.get('id'),
                'email': email,
                'name': user_info.get('name'),
                'picture': user_info.get('avatar_url'),
            }

            # Call the registered GitHub callback handler if it exists to store user data.
            handler = getattr(request.app.state, "callback_handler", None)
            if handler:
                api_token = secrets.token_urlsafe(
                    32)  # ~43 chars, hard to guess

                # Call the registered handler (await if async)
                await handler('github', user_data, api_token)

                redirect = RedirectResponse(url="/", status_code=302)
                redirect.set_cookie(
                    key="api_token",
                    value=api_token,
                    httponly=True,
                    secure=True
                )

                return redirect

            # Handler not set - log and raise error to prevent silent failure
            logging.error(
                "GitHub OAuth callback handler not registered in app state")
            raise HTTPException(
                status_code=500, detail="Authentication handler not configured")

        # If we reach here, user_info was falsy
        logging.warning("No user info received from GitHub OAuth")
        raise HTTPException(
            status_code=400, detail="Failed to get user info from Github")

    except Exception as e:
        logging.error("GitHub OAuth authentication failed: %s",
                      str(e))  # nosemgrep
        raise HTTPException(
            status_code=400, detail="Authentication failed") from e


@auth_router.get("/login/github/callback", response_class=RedirectResponse)
async def github_callback_compat(request: Request) -> RedirectResponse:
    """Handle GitHub OAuth callback redirect for compatibility."""
    qs = f"?{request.url.query}" if request.url.query else ""
    redirect = f"/login/github/authorized{qs}"
    return RedirectResponse(url=redirect, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@auth_router.get("/auth-status")
def auth_status(request: Request) -> JSONResponse:
    """Check authentication status via PostgreSQL token lookup."""
    api_token = request.cookies.get("api_token")
    if not api_token:
        return JSONResponse(content={"authenticated": False}, status_code=200)

    db = next(get_db_session())
    try:
        user = get_user_by_token(db, api_token)
        if not user:
            return JSONResponse(content={"authenticated": False}, status_code=200)

        return JSONResponse(
            content={
                "authenticated": True,
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "name": f"{user.first_name} {user.last_name}".strip(),
                    "picture": None,
                    "role": user.role.value,
                }
            }
        )
    finally:
        db.close()


@auth_router.get("/logout")
@auth_router.post("/logout")
def logout(request: Request):
    """Handle user logout — delete token from PostgreSQL."""
    api_token = request.cookies.get("api_token")

    if api_token:
        db = next(get_db_session())
        try:
            delete_token(db, api_token)
        finally:
            db.close()

    if request.method == "GET":
        response = RedirectResponse(url="/", status_code=302)
    else:
        response = JSONResponse(content={"success": True})

    if api_token:
        response.delete_cookie("api_token")
    return response

class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    isActive: Optional[bool] = None


@auth_router.get("/users")
def get_users_list(request: Request) -> JSONResponse:
    """Trả về danh sách users (Chỉ dành cho Admin)."""
    api_token = request.cookies.get("api_token")
    if not api_token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)

    db = next(get_db_session())
    try:
        current_user = get_user_by_token(db, api_token)
        if not current_user or current_user.role != UserRole.ADMIN:
            return JSONResponse({"detail": "Permission denied"}, status_code=status.HTTP_403_FORBIDDEN)

        from api.auth.user_management import list_all_users
        users = list_all_users(db)
        return JSONResponse(
            content=[
                {
                    "id": str(u.id),
                    "email": u.email,
                    "firstName": u.first_name,
                    "lastName": u.last_name,
                    "role": u.role.value,
                    "isActive": u.is_active,
                    "createdAt": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ]
        )
    finally:
        db.close()


@auth_router.put("/users/{user_id}")
def update_user_profile(request: Request, user_id: str, payload: UpdateUserRequest) -> JSONResponse:
    """Cập nhật quyền và trạng thái hoạt động của user (Chỉ dành cho Admin)."""
    api_token = request.cookies.get("api_token")
    if not api_token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)

    db = next(get_db_session())
    try:
        current_user = get_user_by_token(db, api_token)
        if not current_user or current_user.role != UserRole.ADMIN:
            return JSONResponse({"detail": "Permission denied"}, status_code=status.HTTP_403_FORBIDDEN)

        role_enum = None
        if payload.role:
            try:
                role_enum = UserRole(payload.role)
            except ValueError:
                return JSONResponse({"detail": "Invalid role value"}, status_code=status.HTTP_400_BAD_REQUEST)

        from api.auth.user_management import update_user_role_and_status
        updated = update_user_role_and_status(
            db,
            target_user_id=user_id,
            role=role_enum,
            is_active=payload.isActive,
        )
        if not updated:
            return JSONResponse({"detail": "User not found"}, status_code=status.HTTP_404_NOT_FOUND)

        return JSONResponse({"success": True})
    finally:
        db.close()

class CreateUserRequest(BaseModel):
    firstName: str
    lastName: str = ""
    email: str
    password: str
    role: str = "analyst"


@auth_router.post("/users")
def create_user(request: Request, payload: CreateUserRequest) -> JSONResponse:
    """Admin tạo tài khoản mới cho user khác."""
    api_token = request.cookies.get("api_token")
    if not api_token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)

    db = next(get_db_session())
    try:
        current_user = get_user_by_token(db, api_token)
        if not current_user or current_user.role != UserRole.ADMIN:
            return JSONResponse({"detail": "Permission denied"}, status_code=status.HTTP_403_FORBIDDEN)

        try:
            role_enum = UserRole(payload.role)
        except ValueError:
            return JSONResponse({"detail": "Invalid role value"}, status_code=status.HTTP_400_BAD_REQUEST)

        from api.auth.user_management import create_user_by_admin
        try:
            new_user = create_user_by_admin(
                db,
                email=payload.email,
                password=payload.password,
                first_name=payload.firstName,
                last_name=payload.lastName,
                role=role_enum,
            )
        except ValueError as e:
            return JSONResponse({"detail": str(e)}, status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(
            content={
                "id": str(new_user.id),
                "email": new_user.email,
                "firstName": new_user.first_name,
                "lastName": new_user.last_name,
                "role": new_user.role.value,
                "isActive": new_user.is_active,
                "createdAt": new_user.created_at.isoformat() if new_user.created_at else None,
            },
            status_code=status.HTTP_201_CREATED,
        )
    finally:
        db.close()


@auth_router.delete("/users/{user_id}")
def delete_user(request: Request, user_id: str) -> JSONResponse:
    """Admin xóa tài khoản người dùng."""
    api_token = request.cookies.get("api_token")
    if not api_token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)

    db = next(get_db_session())
    try:
        current_user = get_user_by_token(db, api_token)
        if not current_user or current_user.role != UserRole.ADMIN:
            return JSONResponse({"detail": "Permission denied"}, status_code=status.HTTP_403_FORBIDDEN)

        if str(current_user.id) == user_id:
            return JSONResponse({"detail": "Cannot delete your own account"}, status_code=status.HTTP_400_BAD_REQUEST)

        from api.auth.user_management import delete_user_by_admin
        deleted = delete_user_by_admin(db, user_id)
        if not deleted:
            return JSONResponse({"detail": "User not found"}, status_code=status.HTTP_404_NOT_FOUND)

        return JSONResponse({"success": True})
    finally:
        db.close()




def init_auth(app):
    """Initialize OAuth and sessions for the app."""

    config = Config(environ=os.environ)
    oauth = OAuth(config)

    # Only register Google OAuth if credentials are available
    if _is_google_auth_enabled():
        oauth.register(
            name="google",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            api_base_url="https://openidconnect.googleapis.com/v1/",
            client_kwargs={"scope": "openid email profile"},
        )
        logging.info("Google OAuth initialized successfully")
    else:
        logging.info("Google OAuth not configured - skipping registration")

    # Only register GitHub OAuth if credentials are available
    if _is_github_auth_enabled():
        oauth.register(
            name="github",
            client_id=os.getenv("GITHUB_CLIENT_ID"),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "user:email"},
        )
        logging.info("GitHub OAuth initialized successfully")
    else:
        logging.info("GitHub OAuth not configured - skipping registration")

    app.state.oauth = oauth
