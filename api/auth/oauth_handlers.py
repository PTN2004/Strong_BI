import logging
from typing import Dict, Any

from fastapi import FastAPI
from authlib.integrations.starlette_client import OAuth


def setup_oauth_handlers(app: FastAPI, oauth: OAuth):
    app.state.oauth = oauth

    async def handle_callback(provider: str, user_info: Dict[str, Any], api_token: str):
        """
        OAuth callback handler.
        NOTE: OAuth (Google/GitHub) logins are not the primary auth method in this system.
        The primary method is local email/password stored in PostgreSQL.
        This handler is kept for backward compatibility only.
        """
        try:
            email = user_info.get("email")
            if not email:
                logging.error("Missing email from %s OAuth response", provider)
                return False
            logging.info("OAuth login via %s for email: %s (not persisted to PG)", provider, email)
            return True
        except Exception as exc:
            logging.error("Error handling %s OAuth callback: %s", provider, exc)
            return False

    app.state.callback_handler = handle_callback
