"""
Catalog and related data tools (search, details, column profile, relationships, lineage).
"""

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

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

_DESC_SEARCH = (
    "Search the OvalEdge catalog (Elasticsearch hybrid search). Use for discovery: "
    "tables, files, glossary entries, tags. Supports free text, pagination, "
    "governance filters (owner, steward, custodian), and connection/schema scope.\n\n"
    f"Backend: GET {MCP_PATH_SEARCH_CATALOG} (query params: searchTerm, page, limit, "
    "connectionName, schemaName, owner, steward, custodian, objectType).\n\n"
    "object_type must be one of: oetable, oefile, glossary, oetag — or omit to search all."
)
_DESC_DETAILS = (
    "Fetch one catalog document (JSON from Elasticsearch; embeddings removed). "
    "Use after search_catalog_assets to drill into an asset.\n\n"
    f"Backend: GET {MCP_PATH_OBJECT_DETAILS}\n\n"
    "Exactly one lookup mode: (1) fully_qualified_name alone, OR "
    "(2) object_id AND object_type together. Never mix FQN with id/type.\n\n"
    "object_type: oetable | oefile | glossary | oetag."
)
_DESC_COLUMN = (
    "Column-level profile statistics for one table or file asset.\n\n"
    f"Backend: GET {MCP_PATH_COLUMN_PROFILE}\n\n"
    "object_type must be oetable or oefile only."
)
_DESC_REL = (
    "Table-only: entity relationships (columns, patterns) for one oetable.\n\n"
    f"Backend: GET {MCP_PATH_ENTITY_RELATIONSHIPS}\n\n"
    "Pass the table's internal object_id (oetable)."
)
_DESC_LINEAGE = (
    "Data lineage graph from the database for a table or file.\n\n"
    f"Backend: GET {MCP_PATH_LINEAGE}\n\n"
    "object_type must be oetable or oefile. depth defaults to 2; server may clamp depth."
)


def _q(**kwargs: object) -> dict[str, object]:
    """Omit None values from query params."""
    return {k: v for k, v in kwargs.items() if v is not None}


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_SEARCH)
    async def search_catalog_assets(
        search_term: Annotated[
            str | None,
            Field(
                description="Free-text search (maps to API searchTerm). Omit to page/filter only.",
                default=None,
            ),
        ] = None,
        page: Annotated[
            int,
            Field(description="1-based page index (default 1).", ge=1),
        ] = 1,
        limit: Annotated[
            int,
            Field(description="Page size (default 20; capped at 100 for this client).", ge=1),
        ] = 20,
        connection_name: Annotated[
            str | None,
            Field(
                description="Filter by data connection name (API: connectionName).",
                default=None,
            ),
        ] = None,
        schema_name: Annotated[
            str | None,
            Field(description="Filter by schema name (API: schemaName).", default=None),
        ] = None,
        owner: Annotated[
            str | None,
            Field(description="Filter by asset owner login/name.", default=None),
        ] = None,
        steward: Annotated[
            str | None,
            Field(description="Filter by steward login/name.", default=None),
        ] = None,
        custodian: Annotated[
            str | None,
            Field(description="Filter by custodian login/name.", default=None),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                description=(
                    "Restrict to one type: oetable, oefile, glossary, oetag. Omit for all types."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """OvalEdge catalog search (see MCP tool description)."""
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

    @mcp.tool(description=_DESC_DETAILS)
    async def catalog_asset_details(
        object_id: Annotated[
            int | None,
            Field(
                description="Internal catalog id; must be used with object_type (not with FQN).",
                default=None,
            ),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                description="oetable | oefile | glossary | oetag; pair with object_id.",
                default=None,
            ),
        ] = None,
        fully_qualified_name: Annotated[
            str | None,
            Field(
                description="Fully qualified name alone; do not pass object_id/object_type.",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Single catalog document (see MCP tool description)."""
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

    @mcp.tool(description=_DESC_COLUMN)
    async def column_profile_statistics(
        object_id: Annotated[int, Field(description="Table or file internal object id.")],
        object_type: Annotated[
            str,
            Field(description="Must be oetable or oefile."),
        ],
    ) -> dict[str, Any]:
        """Column profile stats (see MCP tool description)."""
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

    @mcp.tool(description=_DESC_REL)
    async def table_entity_relationships(
        object_id: Annotated[int, Field(description="oetable internal object id.")],
    ) -> dict[str, Any]:
        """Table entity relationships (see MCP tool description)."""
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_ENTITY_RELATIONSHIPS,
                    params={"objectId": object_id},
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_LINEAGE)
    async def asset_lineage(
        object_id: Annotated[int, Field(description="Table or file internal object id.")],
        object_type: Annotated[
            str,
            Field(description="oetable or oefile."),
        ],
        depth: Annotated[
            int,
            Field(description="Lineage depth (default 2); server may clamp.", ge=0),
        ] = 2,
    ) -> dict[str, Any]:
        """Asset lineage graph (see MCP tool description)."""
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
