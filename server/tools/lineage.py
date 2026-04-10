from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_asset_lineage(
        object_id: str,
        direction: str = "BOTH",
        depth: int = 2,
        include_columns: bool = False,
    ) -> dict[str, Any]:
        """
        Returns the data lineage graph for a given asset.

        Blue lines = auto-lineage (SQL-parsed, system-detected).
        Orange lines = manual lineage (human-defined).
        Both are returned with lineage_type flagged per edge.

        Restricted nodes the user cannot access are returned as:
        {id, name: '[Restricted]', accessible: false}
        — enforced by OvalEdge, not by the MCP.

        Args:
            object_id: The asset to trace lineage for
            direction: UPSTREAM, DOWNSTREAM, or BOTH (default)
            depth: Hops to traverse (default 2, max 5)
            include_columns: Include column-level lineage where available

        TODO: confirm endpoint path from OvalEdge API docs
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    f"/api/mcp/lineage/{object_id}",  # TODO: confirm path
                    params={
                        "direction": direction,
                        "depth": min(depth, 5),
                        "includeColumns": include_columns,
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
