"""Shared helpers for MCP catalog/governance resources."""

from __future__ import annotations

import json

from server.mcp_response_slim import slim_mcp_tool_payload
from server.tools.common.runtime import ovaledge_client


async def fetch_object_details_json(object_id: str, object_type: str) -> str:
    from server.constants import MCP_PATH_OBJECT_DETAILS

    async with ovaledge_client() as client:
        result = await client.get(
            MCP_PATH_OBJECT_DETAILS,
            params={"objectId": int(object_id), "objectType": object_type},
        )
    if isinstance(result, dict):
        result = slim_mcp_tool_payload(result)
    return json.dumps(result, indent=2)
