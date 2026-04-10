from typing import Any

from fastmcp import FastMCP

from server.config import settings
from server.docs import register as register_docs
from server.prompts import workflows
from server.resources import catalog as catalog_res
from server.resources import glossary as glossary_res
from server.resources import lineage as lineage_res
from server.tools import catalog, docs, glossary, lineage, relationships


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
            "Phase 1 — Asset & Metadata Discovery (read-only). "
            "Use tools to search and retrieve governed metadata. "
            "Use resources to read specific assets, terms, and lineage by URI. "
            "Use prompts to run pre-packaged governance workflows. "
            "Every response includes full governance context — ownership, "
            "certification, DQ score, classifications. Never strip this context. "
            "RBAC is enforced by OvalEdge — users see only what they are entitled to."
        ),
        lifespan=lifespan,
    )

    catalog.register(mcp)
    glossary.register(mcp)
    lineage.register(mcp)
    relationships.register(mcp)
    docs.register(mcp)

    catalog_res.register(mcp)
    glossary_res.register(mcp)
    lineage_res.register(mcp)

    workflows.register(mcp)

    register_docs(mcp)

    return mcp


# Shared instance for remote entrypoint and imports that expect a single app.
mcp = create_mcp()
