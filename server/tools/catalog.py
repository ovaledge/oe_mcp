"""
Catalog and related data tools (search, details, column profile, relationships, lineage).
"""

from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_PATH_COLUMN_PROFILE,
    MCP_PATH_ENTITY_RELATIONSHIPS,
    MCP_PATH_LINEAGE,
    MCP_PATH_OBJECT_DETAILS,
    MCP_PATH_SEARCH_CATALOG,
)

# Allowed objectType values for search / details per platform API.
_SEARCH_OBJECT_TYPES = frozenset({"oetable", "oefile", "glossary", "oetag"})
_TABLE_FILE_TYPES = frozenset({"oetable", "oefile"})


def _q(**kwargs: object) -> dict[str, object]:
    """Omit None values from query params."""
    return {k: v for k, v in kwargs.items() if v is not None}


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_catalog_assets(
        search_term: str | None = None,
        page: int = 1,
        limit: int = 20,
        connection_name: str | None = None,
        schema_name: str | None = None,
        owner: str | None = None,
        steward: str | None = None,
        custodian: str | None = None,
        object_type: str | None = None,
    ) -> dict[str, Any]:
        f"""
        Hybrid catalog search (Elasticsearch). Free text, pagination, governance filters,
        connection/schema scope, and object type filter.

        object_type: oetable | oefile | glossary | oetag (optional).

        GET {MCP_PATH_SEARCH_CATALOG}
        """
        if object_type is not None and object_type not in _SEARCH_OBJECT_TYPES:
            return {
                "error": (
                    f"object_type must be one of {sorted(_SEARCH_OBJECT_TYPES)}, "
                    f"got {object_type!r}"
                ),
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_SEARCH_CATALOG,
                    params=_q(
                        searchTerm=search_term,
                        page=max(page, 1),
                        limit=min(max(limit, 1), 100),
                        connectionName=connection_name,
                        schemaName=schema_name,
                        owner=owner,
                        steward=steward,
                        custodian=custodian,
                        objectType=object_type,
                    ),
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool()
    async def catalog_asset_details(
        object_id: int | None = None,
        object_type: str | None = None,
        fully_qualified_name: str | None = None,
    ) -> dict[str, Any]:
        f"""
        Single catalog document (JSON from Elasticsearch, embeddings stripped).

        Exactly one lookup mode:
        - fully_qualified_name alone, OR
        - both object_id and object_type together.
        Do not mix FQN with id/type.

        object_type: oetable | oefile | glossary | oetag.

        GET {MCP_PATH_OBJECT_DETAILS}
        """
        has_fqn = fully_qualified_name is not None and str(fully_qualified_name).strip() != ""
        has_pair = object_id is not None and object_type is not None
        if has_fqn and (object_id is not None or object_type is not None):
            return {
                "error": (
                    "Use either fully_qualified_name alone, or object_id + object_type "
                    "— not both."
                ),
                "status_code": 400,
            }
        if not has_fqn and not has_pair:
            return {
                "error": "Provide fully_qualified_name, or both object_id and object_type.",
                "status_code": 400,
            }
        if has_pair:
            if object_id is None or object_type is None:
                return {
                    "error": "object_id and object_type must be provided together.",
                    "status_code": 400,
                }
            if object_type not in _SEARCH_OBJECT_TYPES:
                return {
                    "error": (
                        f"object_type must be one of {sorted(_SEARCH_OBJECT_TYPES)}, "
                        f"got {object_type!r}"
                    ),
                    "status_code": 400,
                }
        try:
            async with OvalEdgeClient() as client:
                if has_fqn:
                    od_params: dict[str, object] = _q(
                        fullyQualifiedName=fully_qualified_name,
                    )
                else:
                    od_params = _q(objectId=object_id, objectType=object_type)
                return await client.get(MCP_PATH_OBJECT_DETAILS, params=od_params)
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool()
    async def column_profile_statistics(object_id: int, object_type: str) -> dict[str, Any]:
        f"""
        Column-level profile statistics for one table or file.

        object_type: oetable | oefile only.

        GET {MCP_PATH_COLUMN_PROFILE}
        """
        if object_type not in _TABLE_FILE_TYPES:
            return {
                "error": f"object_type must be oetable or oefile, got {object_type!r}",
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_COLUMN_PROFILE,
                    params={"objectId": object_id, "objectType": object_type},
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool()
    async def table_entity_relationships(object_id: int) -> dict[str, Any]:
        f"""
        Table-only: column and pattern entity relationships for the given oetable.

        GET {MCP_PATH_ENTITY_RELATIONSHIPS}
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_ENTITY_RELATIONSHIPS,
                    params={"objectId": object_id},
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool()
    async def asset_lineage(
        object_id: int,
        object_type: str,
        depth: int = 2,
    ) -> dict[str, Any]:
        f"""
        Data lineage graph from the database.

        object_type: oetable | oefile only. depth is clamped server-side.

        GET {MCP_PATH_LINEAGE}
        """
        if object_type not in _TABLE_FILE_TYPES:
            return {
                "error": f"object_type must be oetable or oefile, got {object_type!r}",
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_LINEAGE,
                    params={
                        "objectId": object_id,
                        "objectType": object_type,
                        "depth": depth,
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
