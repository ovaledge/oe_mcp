from typing import Any

from fastmcp import FastMCP

from server.branding import mcp_server_icons
from server.config import settings
from server.constants import (
    DOCS_RESOURCE_URI_PREFIX,
    MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC,
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_GET_USER_OBJECT_ACCESS,
    TOOL_KNOWLEDGE_SEARCH,
    TOOL_SOURCE_SYSTEM_ACCESS,
)
from server.mcp import register_all

_MCP_WORKFLOWS_RESOURCE_URI = f"{DOCS_RESOURCE_URI_PREFIX}/mcp_workflows"

# Tool names embedded in server instructions (tests assert ⊆ MCP_TOOL_NAMES).
MCP_SERVER_INSTRUCTION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        TOOL_KNOWLEDGE_SEARCH,
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
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
    # MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC already ends with the
    # platform-names-are-not-signals paragraph — do not append it again here.
    f"{MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC} "
    "Present the resolve_object_access 1/2 choice and call no access tools (including "
    f"{TOOL_ASSET_EXPLORER}) until the user replies. "
    "Use MCP tools for catalog discovery, governance lookups, native source access (RDAM), "
    "and governed writes. At session start and before multi-step workflows, governed writes, "
    f"RDAM, catalog ACL, or DQ work, read MCP resource {_MCP_WORKFLOWS_RESOURCE_URI} "
    "(agent routing guide). Read each tool's description before calling; for multi-step "
    "playbooks use workflow prompts listed in that guide. "
    "Present formattedResponse from tools to the user when provided. "
    "Governed writes require write_confirmed_by_user=true only after the user approves "
    "a confirm_create or confirm_update preview. "
    f"Org knowledge and OvalEdge product documentation: {TOOL_KNOWLEDGE_SEARCH} "
    "(Search knowledge & docs). "
    f"Find data assets in the catalog: {TOOL_ASSET_EXPLORER} "
    f"(search across types; omit object_type unless the query implies a type); "
    f"then {TOOL_ASSET_DETAILS} (View asset details) after shortlist — "
    "not for who-has-access. "
    f"Native DB/BI grants (RDAM): {TOOL_SOURCE_SYSTEM_ACCESS} + access_intent_confirmed=native "
    "— not catalog search or catalog ACL. "
    f"OvalEdge catalog ACL (user/role grants on catalog objects): {TOOL_GET_USER_OBJECT_ACCESS} "
    "+ access_intent_confirmed=catalog_acl — not native RDAM. "
    "User-facing links: navLink or redirectUrl from tool responses; never show ovaledge:// URIs. "
    "RBAC is enforced server-side; write tools need appropriate OvalEdge permissions."
)


def create_mcp(lifespan: Any = None) -> FastMCP:
    """
    Build the FastMCP application.

    Pass a lifespan only for local stdio (client_credentials JWT at startup).
    Remote HTTP entrypoints use a separate FastAPI app with AuthMiddleware.
    """
    mcp = FastMCP(
        name=settings.mcp_server_name,
        version=settings.mcp_server_version,
        instructions=_MCP_SERVER_INSTRUCTIONS,
        lifespan=lifespan,
        icons=mcp_server_icons(),
    )
    register_all(mcp)
    return mcp


# Default instance for stdio and tests.
mcp = create_mcp()
