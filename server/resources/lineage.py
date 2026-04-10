import json

from fastmcp import FastMCP

from server.client import OvalEdgeClient


def register(mcp: FastMCP) -> None:

    @mcp.resource("ovaledge://lineage/{object_id}")
    async def lineage_resource(object_id: str) -> str:
        """
        Lineage graph snapshot rooted at a given object (depth 2, both directions).
        URI: ovaledge://lineage/{object_id}

        Designed for quick embedding in AI context without a full tool call.
        Includes nodes (id, name, type, direction, hop, lineage_type,
        certification_status) and edges (from_id, to_id, lineage_type).

        lineage_type: auto (blue — SQL-parsed) or manual (orange — human-defined).

        TODO: confirm endpoint path from OvalEdge API docs
        """
        async with OvalEdgeClient() as client:
            result = await client.get(
                f"/api/mcp/lineage/{object_id}",  # TODO: confirm path
                params={"direction": "BOTH", "depth": 2},
            )
        return json.dumps(result, indent=2)
