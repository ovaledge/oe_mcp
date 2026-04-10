"""
Local MCP entrypoint — stdio transport.
Auth: OvalEdge client_credentials → OvalEdge JWT

Run:
    poetry run oe-mcp-local
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from server.app import create_mcp
from server.auth.context import current_oe_jwt
from server.auth.token_exchange import get_or_refresh_local_token


@asynccontextmanager
async def local_lifespan(_server: object) -> AsyncIterator[dict[str, Any]]:
    """
    FastMCP lifespan hook.
    Obtains OvalEdge JWT via client_credentials and sets it in ContextVar
    within FastMCP's event loop — ContextVar state persists to tool calls.
    """
    token = await get_or_refresh_local_token()
    current_oe_jwt.set(token)
    yield {}


mcp = create_mcp(lifespan=local_lifespan)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
