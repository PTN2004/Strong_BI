import hmac
import logging
import os
import secrets

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.auth.oauth_handlers import setup_oauth_handlers
from api.auth.user_management import SECRET_KEY
from api.database import init_db
from api.routes.auth import auth_router, init_auth
from api.routes.graphs import graphs_router
from api.routes.database import database_router
from api.routes.tokens import tokens_router
from api.routes.settings import settings_router
from api.routes.conversations import conversations_router
from api.routes.dashboards import dashboards_router
from contextlib import asynccontextmanager
from api.graph_db.factory import GraphDatabaseFactory


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Startup
    try:
        await GraphDatabaseFactory.get_instance()
    except Exception as e:
        logging.error("Failed to connect to Graph Database at startup: %s", e)
    
    try:
        init_db()
    except Exception as e:
        logging.error("PostgreSQL init failed: %s", e)
        
    yield
    
    # Shutdown
    try:
        await GraphDatabaseFactory.close_instance()
    except Exception as e:
        logging.error("Error closing Graph Database connection: %s", e)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[94m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[1;91m"
    }
    RESET = "\033[0m"
    
    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        level_name = f"{color}{record.levelname}{self.RESET}"
        time_str = f"\033[90m{self.formatTime(record, '%H:%M:%S')}\033[0m"
        name_str = f"\033[36m[{record.name}]\033[0m"
        msg = record.getMessage()
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            msg += f"\n{color}{record.exc_text}{self.RESET}"
        return f"{time_str} {level_name:<16} {name_str} {msg}"

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter())
root_logger.addHandler(console_handler)

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.ERROR)
logging.getLogger("neo4j.pool").setLevel(logging.ERROR)
logging.getLogger("neo4j.io").setLevel(logging.ERROR)



class SecurityMiddleware(BaseHTTPMiddleware): 
    """Middleware for security checks including static file access"""

    STATIC_PREFIX = "/static/"

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(self.STATIC_PREFIX):
            filename = request.url.path[len(self.STATIC_PREFIX) :]
            if not filename or "../" in filename or filename.endswith("/"):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        response = await call_next(request)

        hsts_value = "max-age=31536000; includeSubDomains; preload"
        response.headers["Strict-Transport-Security"] = hsts_value

        return response


def _is_secure_request(request: Request) -> bool:
    """Determine if the request is over HTTPS."""
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        first_proto = forwarded_proto.split(",")[0].strip().lower()
        return first_proto == "https"
    return request.url.scheme == "https"


class CSRFMiddleware(BaseHTTPMiddleware): 
    """Double Submit Cookie CSRF protection.

    Ensures a csrf_token cookie (readable by JS) exists, setting it
    on the response if the incoming request does not already carry one.
    State-changing requests must echo the cookie value back
    via the X-CSRF-Token header.  Bearer-token authenticated
    requests and auth/login endpoints are exempt.
    """

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
    CSRF_COOKIE = "csrf_token"
    CSRF_HEADER = "x-csrf-token"

    EXEMPT_PREFIXES = (
        "/login/",
        "/signup/",
        "/mcp",
    )

    async def dispatch(self, request: Request, call_next):
        if (
            request.method not in self.SAFE_METHODS
            and not request.url.path.startswith(self.EXEMPT_PREFIXES)
            and not request.headers.get("authorization", "").lower().startswith("bearer ")
        ):
            cookie_token = request.cookies.get(self.CSRF_COOKIE)
            header_token = request.headers.get(self.CSRF_HEADER)

            if (
                not cookie_token
                or not header_token
                or not hmac.compare_digest(cookie_token, header_token)
            ):
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid"},
                )
                self._ensure_csrf_cookie(request, response)
                return response

        response = await call_next(request)
        self._ensure_csrf_cookie(request, response)
        return response

    CSRF_COOKIE_MAX_AGE = 60 * 60 * 24 * 14

    def _ensure_csrf_cookie(self, request: Request, response):
        """Set the CSRF cookie if it is not already present."""
        if not request.cookies.get(self.CSRF_COOKIE):
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                key=self.CSRF_COOKIE,
                value=token,
                httponly=False,  
                samesite="lax",
                secure=_is_secure_request(request),
                path="/",
                max_age=self.CSRF_COOKIE_MAX_AGE,
            )


def create_app(): 
    """Create and configure the FastAPI application."""

    # 1. KHỞI TẠO APP MỘT LẦN DUY NHẤT Ở ĐÂY
    app = FastAPI(
        title="QueryWeaver",
        description="Text2SQL with Graph-Powered Schema Understanding",
        lifespan=app_lifespan,
        openapi_tags=[
            {
                "name": "Authentication",
                "description": "User authentication and OAuth operations",
            },
            {
                "name": "Graphs & Databases",
                "description": "Database schema management and querying",
            },
            {
                "name": "Database Connection",
                "description": "Connect to external databases",
            },
            {
                "name": "API Tokens",
                "description": "Manage API tokens for authentication",
            },
        ]
    )

    # 2. Include routers
    app.include_router(auth_router)
    app.include_router(graphs_router, prefix="/graphs")
    app.include_router(database_router)
    app.include_router(tokens_router, prefix="/tokens")
    app.include_router(settings_router, prefix="/settings")
    app.include_router(conversations_router, prefix="/conversations")
    app.include_router(dashboards_router, prefix="/dashboards")

    # 3. GẮN MCP BẰNG MOUNT (KHÔNG CHẮP VÁ ROUTE)
    disable_mcp = os.getenv("DISABLE_MCP", "false").lower() in ("1", "true", "yes")
    
    if disable_mcp:
        logging.info("MCP endpoints disabled via DISABLE_MCP environment variable")
    else:
        mcp = FastMCP.from_fastapi(
            app=app,
            name="queryweaver",
            route_maps=[
                RouteMap(tags={"mcp_resource"}, mcp_type=MCPType.RESOURCE),
                RouteMap(
                    tags={"mcp_resource_template"},
                    mcp_type=MCPType.RESOURCE_TEMPLATE,
                ),
                RouteMap(tags={"mcp_tool"}, mcp_type=MCPType.TOOL),
                RouteMap(mcp_type=MCPType.EXCLUDE),
            ],
        )
        mcp_app = mcp.http_app(path="/mcp")

        # CÁCH CHUẨN: Gắn mcp_app vào đường dẫn /mcp
        app.mount("/mcp", mcp_app)

    # 4. CUSTOM OPENAPI
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        from fastapi.openapi.utils import get_openapi

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        openapi_schema["components"]["securitySchemes"] = {
            "ApiTokenAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "api_token",
                "description": "API token for programmatic access. "
                "Generate via POST /tokens/generate after OAuth login.",
            },
            "SessionAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "session",
                "description": "Session cookie for web browsers. "
                "Login via Google/GitHub at /login/google or /login/github.",
            },
        }

        for _, path_item in openapi_schema["paths"].items():
            for method, operation in path_item.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    if "401" in operation.get("responses", {}):
                        operation["security"] = [
                            {"ApiTokenAuth": []},  
                            {"SessionAuth": []},  
                        ]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # 5. MIDDLEWARE
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    app.add_middleware(
        SessionMiddleware,
        secret_key=SECRET_KEY,
        same_site="lax",  
        https_only=False,  
        max_age=60 * 60 * 24 * 14,  
    )

    app.add_middleware(SecurityMiddleware)
    app.add_middleware(CSRFMiddleware)

    # 6. STATIC FILES
    dist_path = os.path.join(os.path.dirname(__file__), "../app/dist")
    if os.path.exists(dist_path):
        app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")
        if os.path.exists(os.path.join(dist_path, "icons")):
            app.mount("/icons", StaticFiles(directory=os.path.join(dist_path, "icons")), name="icons")
        if os.path.exists(os.path.join(dist_path, "img")):
            app.mount("/img", StaticFiles(directory=os.path.join(dist_path, "img")), name="img")
        app.mount("/static", StaticFiles(directory=dist_path), name="static")
    else:
        logging.warning("React build directory not found. Run 'cd app && npm run build'")

    # 7. INIT AUTH & HANDLERS
    init_auth(app)
    
    # Kiểm tra xem app.state có oauth không trước khi setup
    if hasattr(app.state, 'oauth'):
        setup_oauth_handlers(app, app.state.oauth)
    else:
        logging.warning("OAuth state not found on app, skipping setup_oauth_handlers")

    # 8. ROUTES PHỤ VÀ EXCEPTION HANDLER
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        favicon_path = os.path.join(dist_path, "favicon.ico")
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path, media_type="image/x-icon")
        return JSONResponse({"error": "Favicon not found"}, status_code=404)

    @app.exception_handler(Exception)
    async def handle_oauth_error(request: Request, exc: Exception): 
        if "token" in str(exc).lower() or "oauth" in str(exc).lower():
            logging.warning("OAuth error occurred: %s", exc)
            return RedirectResponse(url="/", status_code=302)
        if isinstance(exc, HTTPException):
            raise exc
        raise exc

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_app(full_path: str): 
        index_path = os.path.join(dist_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse({"error": "React app not found"}, status_code=404)

    return app