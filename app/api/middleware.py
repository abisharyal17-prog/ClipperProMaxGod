"""ASGI middleware for the Clipper engine: bearer auth.

``AuthMiddleware`` rejects unauthenticated ``/api`` and ``/media`` requests with a
structured ``401`` before they reach a route. CORS (including Private Network
Access, which lets the HTTPS-hosted UI reach ``http://127.0.0.1``) is configured
directly on ``CORSMiddleware`` in ``server.py``.
"""

from __future__ import annotations

from urllib.parse import unquote

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app import auth

#: Paths that never require a token (bootstrap endpoints the UI probes).
PUBLIC_PREFIXES = ("/api/health", "/api/auth/status")
#: Paths that always require a token.
PROTECTED_PREFIXES = ("/api/", "/media/")


def is_protected(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        return False
    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _headers(scope: Scope) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


def _query_token(scope: Scope) -> str | None:
    query = scope.get("query_string", b"").decode("latin-1")
    for pair in query.split("&"):
        key, _, value = pair.partition("=")
        if key == "token" and value:
            return unquote(value)
    return None


def token_from_scope(scope: Scope) -> str | None:
    """Token from the ``Authorization`` header or a ``token=`` query parameter.

    The query parameter exists because ``<video src>`` and ``WebSocket`` cannot
    send custom headers.
    """
    return auth.token_from_header(_headers(scope).get("authorization")) or _query_token(
        scope
    )


def authorized(scope: Scope) -> bool:
    return auth.verify(token_from_scope(scope))


class AuthMiddleware:
    """Reject unauthenticated API/media traffic with a structured 401."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not auth.auth_enabled():
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        if method == "OPTIONS" or not is_protected(path) or authorized(scope):
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            status_code=401,
            content={
                "detail": {
                    "code": "unauthorized",
                    "message": (
                        "Missing or invalid engine token. "
                        "Re-open the app from a launch link."
                    ),
                }
            },
        )
        await response(scope, receive, send)
