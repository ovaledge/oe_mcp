from typing import Any

from fastmcp import FastMCP

from server.config import settings
from server.mcp import register_all


def create_mcp(lifespan: Any = None) -> FastMCP:
    """
    Build the FastMCP application.

    Pass a lifespan only for local stdio (client_credentials JWT at startup).
    Remote Lambda uses the default lifespan and sets JWT per request in middleware.
    """
    mcp = FastMCP(
        name=settings.mcp_server_name,
        version=settings.mcp_server_version,
        instructions=(
            "OvalEdge data governance MCP. Use tools for catalog search/details, lineage, "
            "glossary, tags, data stories, native RDAM access, and governed writes.\n\n"
            "Routing: org policies/playbooks → lookup_datastory; physical datasets → "
            "search_catalog_assets; OvalEdge product how-to → search_platform_docs; "
            "Redshift/Snowflake/Tableau native grants → source_system_access (never catalog "
            "search as fallback).\n\n"
            "Governed writes (create_glossary_term, create_tag, update_asset_descriptions, "
            "update_governance_roles): show confirm_create/confirm_update preview, then "
            "create_confirmed_by_user=true only after explicit user approval.\n\n"
            "Present formattedResponse and storyCitation verbatim from governance tools. "
            "User-facing links: redirectUrl/navLink — not ovaledge:// URIs.\n\n"
            "Workflow prompts (docs://ovaledge/mcp_workflows) cover multi-step flows. "
            "RBAC enforced by OvalEdge."
        ),
        lifespan=lifespan,
    )

    register_all(mcp)
    return mcp


# Shared instance for remote entrypoint and imports that expect a single app.
mcp = create_mcp()
