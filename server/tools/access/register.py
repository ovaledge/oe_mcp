"""MCP tool registration for catalog object access discovery."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import MCP_PATH_GET_USER_OBJECT_ACCESS
from server.tools.access.helpers import (
    _DESC_GET_USER_OBJECT_ACCESS,
    enrich_get_user_object_access_response,
    validate_get_user_object_access_args,
)
from server.tools.common import drop_none, map_ovaledge_error, ovaledge_client


async def _invoke_get_user_object_access(
    query_direction: str,
    username: str | None,
    object_id: int | None,
    object_type: str | None,
    fully_qualified_name: str | None,
    object_name: str | None,
    resolve_all_matches: bool,
) -> dict[str, Any]:
    err = validate_get_user_object_access_args(
        query_direction,
        username,
        object_id,
        object_type,
        fully_qualified_name,
        object_name,
    )
    if err is not None:
        return err
    params: dict[str, object] = drop_none(
        queryDirection=query_direction.strip().lower(),
        username=username.strip() if username else None,
        objectId=object_id,
        objectType=object_type.strip() if object_type else None,
        fullyQualifiedName=fully_qualified_name.strip() if fully_qualified_name else None,
        objectName=object_name.strip() if object_name else None,
        resolveAllMatches=resolve_all_matches if resolve_all_matches else None,
    )
    try:
        async with ovaledge_client() as client:
            result = await client.get(MCP_PATH_GET_USER_OBJECT_ACCESS, params=params)
            return enrich_get_user_object_access_response(result)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


def register(mcp: FastMCP) -> None:
    @mcp.tool(description=_DESC_GET_USER_OBJECT_ACCESS)
    async def get_user_object_access(
        query_direction: Annotated[
            Literal["user_to_object", "object_to_principals"],
            Field(description="user_to_object: effective access for one user on one asset. "
                  "object_to_principals: all users and roles with access on one asset."),
        ],
        username: Annotated[
            str | None,
            Field(description="Target OvalEdge user id (required for user_to_object)."),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(description="Catalog object id from search_catalog_assets."),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                description=(
                    "Catalog object type (e.g. oetable, oeschema, connection/connector)."
                ),
            ),
        ] = None,
        fully_qualified_name: Annotated[
            str | None,
            Field(description="Fully qualified catalog name when id/type are unknown."),
        ] = None,
        object_name: Annotated[
            str | None,
            Field(
                description=(
                    "Partial or exact asset name; may return matchCandidates. "
                    "For connectors use the connection display name (e.g. looker, Looker_QA) "
                    "with object_type=connection, or a phrase ending in \"connector\"."
                ),
            ),
        ] = None,
        resolve_all_matches: Annotated[
            bool,
            Field(
                description=(
                    "When object_name matches multiple assets, resolve all (default false)."
                ),
            ),
        ] = False,
    ) -> dict[str, Any]:
        return await _invoke_get_user_object_access(
            query_direction,
            username,
            object_id,
            object_type,
            fully_qualified_name,
            object_name,
            resolve_all_matches,
        )
