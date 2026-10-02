"""
Local MCP entrypoint — stdio transport.
Auth: OvalEdge client_credentials → OvalEdge JWT

Run:
    poetry run oe-mcp-local
"""

import os

# Must be set before ``server.app`` import so stdio skips the data-URI icon payload.
os.environ.setdefault("MCP_STDIO_TRANSPORT", "true")
# Stdio stdout is JSON-RPC only. FastMCP's Rich banner / update-check box go to
# stderr; Cursor treats that as a crash and restarts the process before
# tools/list completes, leaving the server "connected" with 0 tools.
os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")
os.environ.setdefault("FASTMCP_CHECK_FOR_UPDATES", "off")
os.environ.setdefault("FASTMCP_ENABLE_RICH_LOGGING", "false")
os.environ.setdefault("FASTMCP_LOG_LEVEL", "WARNING")

import logging
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
    configure_runtime_observability(level=logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
