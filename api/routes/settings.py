"""Settings and configuration routes for the text2sql API."""

import logging
import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from litellm import completion
from sqlalchemy.orm import Session

from api.auth.user_management import token_required
from api.routes.tokens import UNAUTHORIZED_RESPONSE
from api.database import get_db_session
from api.auth.models import User

settings_router = APIRouter(tags=["Settings"])


def _sanitize_for_log(value: str) -> str:
    """Remove control characters that could enable log injection."""
    return str(value).replace("\r", "").replace("\n", "").replace("\t", " ")


class ValidateKeyRequest(BaseModel):
    """Request model for API key validation."""
    api_key: str
    vendor: str = "openai"
    model: str = "gpt-3.5-turbo"
    api_base: str | None = None


@settings_router.post("/validate-api-key", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
async def validate_api_key(request: Request, data: ValidateKeyRequest):  # pylint: disable=too-many-return-statements,unused-argument

    api_key = data.api_key.strip()
    vendor = data.vendor.lower()
    model = data.model

    if not api_key:
        return JSONResponse(
            content={"valid": False, "error": "API key is required"},
            status_code=400
        )

    # Validate vendor — only key-based vendors can be validated via API call
    validatable_vendors = ("openai", "anthropic", "gemini", "cohere", "openrouter")
    if vendor not in validatable_vendors:
        allowed = ", ".join(validatable_vendors)
        return JSONResponse(
            content={"valid": False, "error": f"Unsupported vendor for key validation. Supported: {allowed}"},
            status_code=400
        )

    # Validate model is not empty
    if not model or not model.strip():
        return JSONResponse(
            content={"valid": False, "error": "Model name is required"},
            status_code=400
        )

    # Validate key format based on vendor
    if vendor == "openai" and not api_key.startswith('sk-'):
        return JSONResponse(
            content={"valid": False, "error": "Invalid OpenAI API key format"},
            status_code=400
        )
    if vendor == "anthropic" and not api_key.startswith('sk-ant-'):
        return JSONResponse(
            content={"valid": False, "error": "Invalid Anthropic API key format"},
            status_code=400
        )

    try:
        # Construct model name for LiteLLM (vendor/model format)
        full_model_name = f"{vendor}/{model}"

        test_response = completion(
            model=full_model_name,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1,
            api_key=api_key,
            api_base=data.api_base,
        )

        # If we get here without exception, the key is valid
        if test_response and test_response.choices:
            return JSONResponse(
                content={"valid": True},
                status_code=200
            )
        return JSONResponse(
            content={"valid": False, "error": "Invalid API key"},
            status_code=401
        )

    except Exception as e:  # pylint: disable=broad-except
        error_lower = str(e).lower()
        logging.warning("API key validation failed for vendor=%s",
                        _sanitize_for_log(vendor))

        # Return generic messages — never expose exception details
        if "invalid" in error_lower or "authentication" in error_lower:
            return JSONResponse(
                content={"valid": False, "error": "Invalid API key"},
                status_code=401
            )
        if "quota" in error_lower or "rate" in error_lower:
            return JSONResponse(
                content={"valid": False, "error": "API quota exceeded or rate limited"},
                status_code=429
            )
        return JSONResponse(
            content={"valid": False, "error": "Failed to validate API key"},
            status_code=500
        )


@settings_router.get("/system-info")
def get_system_info() -> JSONResponse:
    """Trả về thông tin cấu hình hệ thống (GraphDB đang dùng, LLM mặc định)."""
    neo4j_url = os.getenv("NEO4J_URL", "").strip()
    graph_db_type = "Neo4j" if neo4j_url else "FalkorDB"
    
    from api.config import Config
    default_llm = Config.LLM_PROVIDER
    
    return JSONResponse(
        content={
            "graphDbType": graph_db_type,
            "defaultLlmProvider": default_llm,
            "hasNeo4jUrl": bool(neo4j_url),
            "hasFalkorDbUrl": bool(os.getenv("FALKORDB_URL")),
            "hasVllmModel": bool(os.getenv("VLLM_MODEL")),
            "hasOllamaModel": bool(os.getenv("OLLAMA_MODEL")),
        }
    )


class UpdateLLMProviderRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_api_base: str | None = None

@settings_router.get("/llm-provider", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
def get_llm_provider(request: Request) -> JSONResponse:
    """Trả về cấu hình LLM của người dùng hiện tại."""
    user = getattr(request.state, "user", {})
    return JSONResponse(content={
        "llm_provider": user.get("llm_provider"),
        "llm_model": user.get("llm_model"),
        # To mask API key if needed, or return as is so frontend can populate the form
        "llm_api_key": user.get("llm_api_key"), 
        "llm_api_base": user.get("llm_api_base"),
    })

@settings_router.put("/llm-provider", responses={401: UNAUTHORIZED_RESPONSE})
@token_required
def update_llm_provider(
    request: Request,
    data: UpdateLLMProviderRequest,
    db: Session = Depends(get_db_session)
) -> JSONResponse:
    """Cập nhật cấu hình LLM riêng của người dùng."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(content={"error": "User not found"}, status_code=404)
        
    user.llm_provider = data.llm_provider
    user.llm_model = data.llm_model
    user.llm_api_key = data.llm_api_key
    user.llm_api_base = data.llm_api_base
    db.commit()
    
    return JSONResponse(content={"success": True, "message": "LLM provider updated"})
