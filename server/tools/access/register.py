"""MCP tool registration for catalog object access discovery."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_ACCESS_INTENT_CATALOG_ACL,
    MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC,
    MCP_ACCESS_USER_QUESTION_FIELD_DOC,
    MCP_PATH_GET_USER_OBJECT_ACCESS,
)
from server.tools.access.disambiguation import validate_access_intent_confirmed
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
    access_intent_confirmed: str | None = None,
    user_question: str | None = None,
) -> dict[str, Any]:
    intent_err = validate_access_intent_confirmed(
        access_intent_confirmed,
        query_direction=query_direction,
        expected_intent=MCP_ACCESS_INTENT_CATALOG_ACL,
        user_question=user_question,
    )
    if intent_err is not None:
        return intent_err
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
        access_intent_confirmed: Annotated[
            Literal["native", "catalog_acl"] | None,
            Field(
                default=None,
                description=MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC,
            ),
        ] = None,
        user_question: Annotated[
            str | None,
            Field(
                default=None,
                description=MCP_ACCESS_USER_QUESTION_FIELD_DOC,
            ),
        ] = None,
    ) -> dict[str, Any]:
        return await _invoke_get_user_object_access(
            query_direction,
            username,
            object_id,
            object_type,
            fully_qualified_name,
            object_name,
            resolve_all_matches,
            access_intent_confirmed,
            user_question,
        )
