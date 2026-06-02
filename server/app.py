from typing import Any

from fastmcp import FastMCP

from server.config import settings
from server.docs import register as register_docs
from server.prompts import workflows
from server.resources import catalog as catalog_res
from server.resources import governance as governance_res
from server.tools import catalog, data_access_management, docs, governance


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
            "You are connected to the OvalEdge data governance platform. "
            "Use tools for catalog discovery (search, details, profiles, lineage, "
            "metadata drift), governance lookups (glossary, tags, data stories), "
            "source-system access previews, and governed write operations where the "
            "API allows (e.g. create_tag, update_asset_descriptions, update_governance_roles). "
            "For native Redshift/Snowflake/Tableau grants (not OvalEdge catalog ACLs), "
            "use get_source_system_access. "
            "Use resources for deep links: catalog tables and glossary terms by id. "
            "Use prompts to run pre-packaged governance workflows. "
            "Every response includes full governance context where the API provides it. "
            "RBAC is enforced by OvalEdge — users see only what they are entitled to; "
            "write tools require appropriate OvalEdge permissions."
        ),
        lifespan=lifespan,
    )

    catalog.register(mcp)
    data_access_management.register(mcp)
    governance.register(mcp)
    docs.register(mcp)

    catalog_res.register(mcp)
    governance_res.register(mcp)

    workflows.register(mcp)

    register_docs(mcp)

    return mcp


# Shared instance for remote entrypoint and imports that expect a single app.
mcp = create_mcp()
