from typing import Any

from fastmcp import FastMCP

from server.branding import mcp_server_icons
from server.config import settings
from server.mcp import register_all

# Routing detail lives in tool descriptions and docs://ovaledge/mcp_workflows — keep
# server instructions short to limit always-on MCP context size.
_MCP_SERVER_INSTRUCTIONS = (
    "You are connected to the OvalEdge data governance platform. "
    "Use MCP tools for catalog discovery, governance lookups, native source access (RDAM), "
    "and governed writes. Read each tool's description before calling; for multi-step playbooks "
    "use workflow prompts or the docs://ovaledge/mcp_workflows resource. "
    "Present formattedResponse from tools to the user when provided. "
    "Governed writes require create_confirmed_by_user=true only after the user approves "
    "a confirm_create or confirm_update preview. "
    "Org knowledge in data stories: lookup_datastory (not search_platform_docs). "
    "Physical datasets: search_catalog_assets; native DB/BI grants: source_system_access only — "
    "never fall back to catalog search for RDAM. "
    "Catalog ACL permissions (user/role grants on catalog objects): get_user_object_access. "
    "Ambiguous who-has-access (no native/remote/DAM/source-system signals): disambiguate first — "
    "workflow prompt resolve_object_access; do not call either access tool until the user picks. "
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
