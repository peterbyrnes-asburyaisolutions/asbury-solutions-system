"""Opt-in bearer auth for ``/api/v{1,2}/memory/*``.

When ``settings.api.auth_token`` is unset or empty the middleware is not
mounted (see :func:`everos.entrypoints.api.app.create_app`). When mounted,
every request whose path is under the memory API prefixes must carry
``Authorization: Bearer <token>`` matching the configured secret; otherwise
the response is HTTP 401. ``OPTIONS`` (CORS preflight), ``/health``, and
``/metrics`` are never gated here.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

_PROTECTED_PREFIXES = ("/api/v1/memory", "/api/v2/memory")


def _is_protected_path(path: str) -> bool:
    return any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in _PROTECTED_PREFIXES
    )


def _bearer_matches(authorization: str | None, expected: str) -> bool:
    if not authorization:
        return False
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        return False
    return secrets.compare_digest(credential, expected)


class MemoryApiAuthMiddleware(BaseHTTPMiddleware):
    """Require bearer token on memory API routes when configured."""

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method == "OPTIONS" or not _is_protected_path(request.url.path):
            return await call_next(request)
        if not _bearer_matches(request.headers.get("Authorization"), self._token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
