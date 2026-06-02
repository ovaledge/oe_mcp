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
            "Phase 1 — Asset & Metadata Discovery (catalog read; glossary create supported). "
            "Use tools to search the catalog, fetch asset details, lineage, profiles, "
            "and governance (glossary lookup, create_glossary_term guided flow, tags). "
            "For new glossary terms: use create_glossary_term (domain → category when "
            "categories exist → subcategory when available; description required; never "
            "invent description); present formattedResponse to the user and wait — never "
            "auto-pick domain_id or skip_category unless the user explicitly skips category. "
            "If user provides a domain name in natural language ('under <domain>'), pass it as "
            "domain_name on the first call; otherwise use domain_id from picker. "
            "Then create with term_name, resolved domain_id, and description. "
            "For native Redshift/Snowflake/Tableau grants (not OvalEdge catalog ACLs), "
            "use get_source_system_access. "
            "Use resources for deep links: catalog tables and glossary terms by id. "
            "Use prompts to run pre-packaged governance workflows. "
            "Every response includes full governance context where the API provides it. "
            "RBAC is enforced by OvalEdge — users see only what they are entitled to."
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
