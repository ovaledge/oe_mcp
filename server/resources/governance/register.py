"""MCP resources for governance assets."""

from __future__ import annotations

from fastmcp import FastMCP

from server.constants import (
    MCP_PATH_OBJECT_DETAILS,
    MCP_RESOURCE_GOVERNANCE_DATA_STORY,
    MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM,
    MCP_RESOURCE_GOVERNANCE_TAG,
)
from server.resources.helpers import fetch_object_details_json


def register(mcp: FastMCP) -> None:

    @mcp.resource(MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM)
    async def glossary_term_resource(object_id: str) -> str:
        f"""
        Glossary term as catalog document (objectType=glossary).
        URI: {MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM}

        GET {MCP_PATH_OBJECT_DETAILS}?objectId=...&objectType=glossary
        """
        return await fetch_object_details_json(object_id, "glossary")

    @mcp.resource(MCP_RESOURCE_GOVERNANCE_DATA_STORY)
    async def data_story_resource(object_id: str) -> str:
        f"""
        Data story catalog document (objectType=oestory) by internal object id.
        URI: {MCP_RESOURCE_GOVERNANCE_DATA_STORY}

        GET {MCP_PATH_OBJECT_DETAILS}?objectId=...&objectType=oestory

        For narrative sections and formattedResponse, prefer lookup_datastory with the same id.
        """
        return await fetch_object_details_json(object_id, "oestory")

    @mcp.resource(MCP_RESOURCE_GOVERNANCE_TAG)
    async def tag_resource(object_id: str) -> str:
        f"""
        Tag catalog document (objectType=oetag) by internal object id.
        URI: {MCP_RESOURCE_GOVERNANCE_TAG}

        GET {MCP_PATH_OBJECT_DETAILS}?objectId=...&objectType=oetag

        For tag hierarchy and create-options context, prefer lookup_tags.
        """
        return await fetch_object_details_json(object_id, "oetag")
