"""
Local MCP entrypoint — stdio transport.
Auth: OvalEdge client_credentials → OvalEdge JWT

Run:
    poetry run oe-mcp-local
"""

import os

# Must be set before ``server.app`` import so branding uses data URI, not a localhost HTTP URL.
os.environ.setdefault("MCP_STDIO_TRANSPORT", "true")

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from server.app import create_mcp
from server.auth.local_lifespan import local_oe_jwt_lifespan
from server.logging_config import configure_runtime_observability


@asynccontextmanager
async def local_lifespan(_server: object) -> AsyncIterator[dict[str, Any]]:
    """FastMCP lifespan hook — delegates to shared local JWT startup."""
    async with local_oe_jwt_lifespan(_server) as state:
        yield state


mcp = create_mcp(lifespan=local_lifespan)


def main() -> None:
    configure_runtime_observability()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
