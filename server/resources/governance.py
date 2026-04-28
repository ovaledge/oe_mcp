import json

from fastmcp import FastMCP

from server.client import OvalEdgeClient
from server.constants import MCP_PATH_OBJECT_DETAILS, MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM


def register(mcp: FastMCP) -> None:

    @mcp.resource(MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM)
    async def glossary_term_resource(object_id: str) -> str:
        f"""
        Glossary term as catalog document (objectType=glossary).
        URI: {MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM}

        GET {MCP_PATH_OBJECT_DETAILS}?objectId=...&objectType=glossary
        """
        async with OvalEdgeClient() as client:
            result = await client.get(
                MCP_PATH_OBJECT_DETAILS,
                params={"objectId": int(object_id), "objectType": "glossary"},
            )
        return json.dumps(result, indent=2)
