from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_entity_relationships(
        object_id: str,
        depth: int = 1,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """
        Returns primary key / foreign key relationships between a table
        and other tables. Tells the AI how tables can be legitimately
        joined — based on structural definitions in the source system.

        Essential for any query that needs to suggest or validate
        multi-table joins.

        Args:
            object_id: Table or file to find relationships for
            depth: Relationship hops (default 1, max 3)
            include_metadata: Include governance metadata per related object

        TODO: confirm endpoint path from OvalEdge API docs
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    f"/api/mcp/assets/{object_id}/relationships",  # TODO: confirm path
                    params={
                        "depth": min(depth, 3),
                        "includeMetadata": include_metadata,
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
