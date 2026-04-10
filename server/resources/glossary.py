import json

from fastmcp import FastMCP

from server.client import OvalEdgeClient


def register(mcp: FastMCP) -> None:

    @mcp.resource("ovaledge://glossary/term/{term_id}")
    async def glossary_term_resource(term_id: str) -> str:
        """
        Full Business Glossary term by ID.
        URI: ovaledge://glossary/term/{term_id}

        Includes: organisational definition, domain/category hierarchy,
        20+ typed relationship vocabulary, associated physical data objects,
        governance roles, classifications, curation score, sync_options.

        TODO: confirm endpoint path from OvalEdge API docs
        """
        async with OvalEdgeClient() as client:
            result = await client.get(
                f"/api/mcp/glossary/terms/{term_id}",  # TODO: confirm path
            )
        return json.dumps(result, indent=2)

    @mcp.resource("ovaledge://glossary/domain/{domain_id}")
    async def glossary_domain_resource(domain_id: str) -> str:
        """
        Business Glossary domain — top-level organisational grouping.
        URI: ovaledge://glossary/domain/{domain_id}

        Includes: domain description, default governance roles,
        default classifications, category/subcategory hierarchy,
        term counts, domain-level sync defaults.

        TODO: confirm endpoint path from OvalEdge API docs
        """
        async with OvalEdgeClient() as client:
            result = await client.get(
                f"/api/mcp/glossary/domains/{domain_id}",  # TODO: confirm path
            )
        return json.dumps(result, indent=2)
