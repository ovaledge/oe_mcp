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
            "You are connected to the OvalEdge data governance platform. "
            "Use tools to search the catalog, fetch asset details, lineage, profiles, and "
            "governance (glossary lookup, create_glossary_term guided flow, tags). "
            "For new glossary terms: use create_glossary_term (domain → category when "
            "categories exist → subcategory when available; description required; never "
            "invent description); present formattedResponse to the user and wait — never "
            "auto-pick domain_id or skip_category unless the user explicitly skips category. "
            "If user provides a domain name in natural language ('under <domain>'), pass it as "
            "domain_name on the first call; otherwise use domain_id from picker. "
            "Then create with term_name, resolved domain_id, and description. "
            "Use tools for catalog discovery (search, details, profiles, lineage, "
            "metadata drift), governance lookups (glossary, tags, data stories), "
            "source-system access previews, and governed write operations where the "
            "API allows (e.g. create_tag, update_asset_descriptions, update_governance_roles). "
            "Governed writes require create_confirmed_by_user=true after the user approves "
            "the confirm_create or confirm_update preview. "
            "Organizational knowledge (policies, playbooks, onboarding narratives, domain "
            "context documented in OvalEdge data stories): call lookup_datastory first — "
            "usually content_query set to the user's question; add story_zone_name or "
            "story_name when they name a zone or title. Present formattedResponse and lead "
            "with storyCitation verbatim. Do not answer from model memory when a story may "
            "exist. Use search_platform_docs only for OvalEdge product how-to (features, UI, "
            "configuration), not for org-specific story content. Use search_catalog_assets "
            "for physical datasets; when hits include oestory, follow with lookup_datastory. "
            "For native Redshift/Snowflake/Tableau grants (not OvalEdge catalog ACLs), "
            "use source_system_access only (Instance/Connector DAA enforced on the server; "
            "RDAM SQL, not Elasticsearch). Never fall back to search_catalog_assets when "
            "source_system_access is empty, errors, or not-found — catalog cannot answer "
            "native DB/BI grants. "
            "Use resources for deep links when you already have object ids: "
            "ovaledge://catalog/table/{id}, ovaledge://catalog/file/{id}, "
            "ovaledge://governance/glossary-term/{id}, "
            "ovaledge://governance/data-story/{id}, "
            "ovaledge://governance/tag/{id}. "
            "Prefer lookup_datastory / lookup_tags for rich formattedResponse. "
            "Use prompts to run pre-packaged governance workflows (discovery, lineage, "
            "stories, tags, metadata drift, native access, creates, DQ, role updates). "
            "Every response includes full governance context where the API provides it. "
            "RBAC is enforced by OvalEdge — users see only what they are entitled to; "
            "write tools require appropriate OvalEdge permissions."
        ),
        lifespan=lifespan,
    )

    register_all(mcp)
    return mcp


# Shared instance for remote entrypoint and imports that expect a single app.
mcp = create_mcp()
