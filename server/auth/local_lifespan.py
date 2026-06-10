"""FastMCP / FastAPI lifespan: obtain OvalEdge JWT for ``AUTH_MODE=local``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from server.auth.context import current_oe_jwt
from server.auth.token_exchange import get_or_refresh_local_token


@asynccontextmanager
async def local_oe_jwt_lifespan(_server: object) -> AsyncIterator[dict[str, Any]]:
    """
    Exchange ``OVALEDGE_USER_TOKEN`` + ``OVALEDGE_USER_SECRET`` for an OvalEdge JWT at startup.

    Used by stdio (``entrypoints/local.py``) and local HTTP (``entrypoints/http_local.py``).
    """
    token = await get_or_refresh_local_token()
    current_oe_jwt.set(token)
    yield {}
