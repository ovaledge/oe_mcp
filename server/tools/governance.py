from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import MCP_PATH_GLOSSARY_TERMS, MCP_PATH_TAGS

_DESC_GLOSSARY = (
    "Look up one business glossary term. Server object type is always glossary.\n\n"
    f"Backend: GET {MCP_PATH_GLOSSARY_TERMS} (objectId OR termName — mutually exclusive).\n\n"
    "Provide either term_name (search by name) or object_id (by id), never both."
)
_DESC_TAGS = (
    "Look up one OETAG (tag) document from Elasticsearch.\n\n"
    f"Backend: GET {MCP_PATH_TAGS} (objectId OR tagName — mutually exclusive).\n\n"
    "Provide either tag_name or object_id, never both."
)


def _q(**kwargs: object) -> dict[str, object]:
    return {k: v for k, v in kwargs.items() if v is not None}


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_GLOSSARY)
    async def lookup_glossary_term(
        object_id: Annotated[
            int | None,
            Field(description="Glossary term internal id; omit if using term_name.", default=None),
        ] = None,
        term_name: Annotated[
            str | None,
            Field(
                description="Term name / label to look up; omit if using object_id.",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Glossary lookup (see MCP tool description)."""
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

    @mcp.tool(description=_DESC_TAGS)
    async def lookup_tags(
        object_id: Annotated[
            int | None,
            Field(description="Tag internal id; omit if using tag_name.", default=None),
        ] = None,
        tag_name: Annotated[
            str | None,
            Field(description="Tag name to look up; omit if using object_id.", default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Tag lookup (see MCP tool description)."""
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
