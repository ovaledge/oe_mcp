import json

from fastmcp import FastMCP

from server.client import OvalEdgeClient


def register(mcp: FastMCP) -> None:

    @mcp.resource("ovaledge://catalog/table/{object_id}")
    async def table_resource(object_id: str) -> str:
        """
        Full metadata for a catalogued database table or view.
        URI: ovaledge://catalog/table/{object_id}

        Includes: identity, governance roles, tags, terms, classifications,
        certification_status, dq_score, curation_score, lineage_status,
        user_access_context. Columns NOT embedded — use include_columns
        param on get_asset_details or ovaledge://catalog/column/{id}.

        TODO: confirm endpoint path from OvalEdge API docs
        """
        async with OvalEdgeClient() as client:
            result = await client.get(
                f"/api/mcp/assets/{object_id}/composite",  # TODO: confirm path
                params={"objectType": "TABLE"},
            )
        return json.dumps(result, indent=2)

    @mcp.resource("ovaledge://catalog/column/{object_id}")
    async def column_resource(object_id: str) -> str:
        """
        Full metadata for a single column.
        URI: ovaledge://catalog/column/{object_id}

        Includes: profiling stats, is_masked, is_restricted, mask_source,
        linked_term, term-inherited classifications and tags.
        mask_source tells whether masking came from a glossary term
        ('term_sync') or was set directly ('direct').

        TODO: confirm endpoint path from OvalEdge API docs
        """
        async with OvalEdgeClient() as client:
            result = await client.get(
                f"/api/mcp/assets/{object_id}/composite",  # TODO: confirm path
                params={"objectType": "COLUMN"},
            )
        return json.dumps(result, indent=2)
