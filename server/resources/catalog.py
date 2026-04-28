import json

from fastmcp import FastMCP

from server.client import OvalEdgeClient
from server.constants import MCP_PATH_OBJECT_DETAILS, MCP_RESOURCE_CATALOG_TABLE


def register(mcp: FastMCP) -> None:

    @mcp.resource(MCP_RESOURCE_CATALOG_TABLE)
    async def table_resource(object_id: str) -> str:
        f"""
        Catalog document for a table (oetable) by internal object id.
        URI: {MCP_RESOURCE_CATALOG_TABLE}

        GET {MCP_PATH_OBJECT_DETAILS}?objectId=...&objectType=oetable
        """
        async with OvalEdgeClient() as client:
            result = await client.get(
                MCP_PATH_OBJECT_DETAILS,
                params={"objectId": int(object_id), "objectType": "oetable"},
            )
        return json.dumps(result, indent=2)
