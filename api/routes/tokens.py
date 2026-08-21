"""Token management routes for the QueryWeaver API."""

import logging
import secrets
from typing import List

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.auth.user_management import token_required
from api.extensions import get_default_db

UNAUTHORIZED_RESPONSE = {"description": "Unauthorized - Please log in or provide a valid API token"}

# Router
tokens_router = APIRouter(tags=["API Tokens"])

class TokenListItem(BaseModel):
    token_id: str
    created_at: int

class TokenListResponse(BaseModel):
    tokens: List[TokenListItem]

@tokens_router.post("/generate", response_model=TokenListItem, responses={
    401: UNAUTHORIZED_RESPONSE
})
@token_required
async def generate_token(request: Request) -> TokenListItem:
    try:
        user_email = request.state.user.get("email")

        handler = getattr(request.app.state, "callback_handler", None)
        if handler:
            api_token = secrets.token_urlsafe(32)  

            user_data = {
                "id": user_email,
                "email": user_email,
                "name": "token token",
                "picture": ""
            }

            await handler('api', user_data, api_token)

            logging.info("Token generated for user: %s", user_email)  

            return TokenListItem(
                token_id=api_token,
                created_at=0  
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate token"
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error generating token: %s", e)  # nosemgrep
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        ) from e

@tokens_router.get("/list", response_model=TokenListResponse, responses={
    401: UNAUTHORIZED_RESPONSE
})
@token_required
async def list_tokens(request: Request) -> TokenListResponse:
    """List all tokens for the authenticated user"""
    try:
        user_email = request.state.user.get("email")

        db = await get_default_db()
        db.select_graph("Organizations")

        query = """
        MATCH(:Identity {email:$user_email, provider:'api'})-[:HAS_TOKEN]->(token:Token)
        RETURN token.id, token.created_at
        """

        result = await db.query(query, {"user_email": user_email})

        tokens = []
        if result.result_set:
            for row in result.result_set:
                tokens.append(TokenListItem(
                    token_id=row[0][-4:],  # last 4 chars in the token_id str
                    created_at=row[1],
                ))

        return TokenListResponse(tokens=tokens)

    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error listing tokens: %s", e)  # nosemgrep
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        ) from e

@tokens_router.delete("/{token_id}", responses={
    401: UNAUTHORIZED_RESPONSE
})
@token_required
async def delete_token(request: Request, token_id: str) -> JSONResponse:
    """Delete a specific token for the authenticated user"""
    try:
        user_email = request.state.user.get("email")

        db = await get_default_db()
        db.select_graph("Organizations")

        # Delete the token
        delete_query = """
        MATCH (user:Identity {email:$user_email, provider:'api'})-[:HAS_TOKEN]->(token:Token)
        WHERE RIGHT(token.id, 4)=$token_id
        DELETE token
        RETURN COUNT(*) AS deleted_count
        """

        result = await db.query(delete_query, {
            "user_email": user_email,
            "token_id": token_id
        })

        sanitized_token_id = token_id.replace('\n', ' ').replace('\r', ' ') if token_id else 'Unknown'  
        logging.info("Token deleted for user %s: token_id=%s", user_email, sanitized_token_id)  

        if result.result_set and result.result_set[0][0] > 0:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "Token deleted successfully"}
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error deleting token: %s", e)  # nosemgrep
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        ) from e
