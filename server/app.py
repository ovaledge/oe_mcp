from typing import Any

from fastmcp import FastMCP

from server.branding import mcp_server_icons
from server.config import settings
from server.constants import (
    TOOL_GET_USER_OBJECT_ACCESS,
    TOOL_LOOKUP_DATASTORY,
    TOOL_SEARCH_CATALOG,
    TOOL_SEARCH_DOCS,
    TOOL_SOURCE_SYSTEM_ACCESS,
)
from server.mcp import register_all

# Tool names embedded in server instructions (tests assert ⊆ MCP_TOOL_NAMES).
MCP_SERVER_INSTRUCTION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        TOOL_LOOKUP_DATASTORY,
        TOOL_SEARCH_DOCS,
        TOOL_SEARCH_CATALOG,
        TOOL_SOURCE_SYSTEM_ACCESS,
        TOOL_GET_USER_OBJECT_ACCESS,
    }
)

# Routing detail lives in tool descriptions and docs://ovaledge/mcp_workflows — keep
# server instructions short to limit always-on MCP context size. Cross-tool disambiguation
# only; enforcement caveats (e.g. never fall back to catalog search for RDAM) live on
# the owning tool descriptions.
_MCP_SERVER_INSTRUCTIONS = (
    "You are connected to the OvalEdge data governance platform. "
    "Use MCP tools for catalog discovery, governance lookups, native source access (RDAM), "
    "and governed writes. Read each tool's description before calling; for multi-step playbooks "
    "use workflow prompts or the docs://ovaledge/mcp_workflows resource. "
    "Present formattedResponse from tools to the user when provided. "
    "Governed writes require write_confirmed_by_user=true only after the user approves "
    "a confirm_create or confirm_update preview. "
    f"Org knowledge in data stories: {TOOL_LOOKUP_DATASTORY} (not {TOOL_SEARCH_DOCS}). "
    f"Physical catalog discovery: {TOOL_SEARCH_CATALOG}. "
    f"Native DB/BI grants (RDAM): {TOOL_SOURCE_SYSTEM_ACCESS} — not catalog search or catalog ACL. "
    f"OvalEdge catalog ACL (user/role grants on catalog objects): {TOOL_GET_USER_OBJECT_ACCESS} "
    "— not native RDAM. "
    "User-facing links: navLink or redirectUrl from tool responses; never show ovaledge:// URIs. "
    "RBAC is enforced server-side; write tools need appropriate OvalEdge permissions."
)


def create_mcp(lifespan: Any = None) -> FastMCP:
    """
    Build the FastMCP application.

    Pass a lifespan only for local stdio (client_credentials JWT at startup).
    Remote Lambda uses the default lifespan and sets JWT per request in middleware.
    """
    mcp = FastMCP(
        name=settings.mcp_server_name,
        version=settings.mcp_server_version,
        icons=mcp_server_icons(),
        instructions=_MCP_SERVER_INSTRUCTIONS,
        lifespan=lifespan,
    )

    register_all(mcp)
    return mcp


# Shared instance for remote entrypoint and imports that expect a single app.
mcp = create_mcp()
