from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import MCP_PATH_GLOSSARY_TERMS, MCP_PATH_TAGS


def _q(**kwargs: object) -> dict[str, object]:
    return {k: v for k, v in kwargs.items() if v is not None}


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def lookup_glossary_term(
        object_id: int | None = None,
        term_name: str | None = None,
    ) -> dict[str, Any]:
        f"""
        Glossary term lookup. Supply either term_name alone or object_id alone — not both.
        Object type is always glossary on the server.

        GET {MCP_PATH_GLOSSARY_TERMS}
        """
        has_id = object_id is not None
        has_name = term_name is not None and str(term_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either object_id or term_name — not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {
                "error": "Provide object_id or term_name.",
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_GLOSSARY_TERMS,
                    params=_q(objectId=object_id, termName=term_name),
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool()
    async def lookup_tags(
        object_id: int | None = None,
        tag_name: str | None = None,
    ) -> dict[str, Any]:
        f"""
        OETAG document from Elasticsearch. Supply either tag_name alone or
        object_id alone — not both.

        GET {MCP_PATH_TAGS}
        """
        has_id = object_id is not None
        has_name = tag_name is not None and str(tag_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either object_id or tag_name — not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {
                "error": "Provide object_id or tag_name.",
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_TAGS,
                    params=_q(objectId=object_id, tagName=tag_name),
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
