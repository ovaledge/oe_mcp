from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_catalog_assets(
        keywords: list[str],
        object_types: list[str] | None = None,
        owner_name: str | None = None,
        steward_name: str | None = None,
        dq_score_min: int | None = None,
        certification_status: str | None = None,
        connection_name: str | None = None,
        has_lineage: bool | None = None,
        is_cde: bool | None = None,
        sort_by: str = "RELEVANCE",
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Primary entry point for metadata discovery.
        Searches the OvalEdge Data Catalog using hybrid search
        (vector + BM25 keyword) with optional governance filters.

        Every result includes full governance context:
        owner, steward, certification_status, dq_score,
        curation_score, classifications, user_access_context.

        Args:
            keywords: Search terms — natural language or technical names
            object_types: Filter by TABLE, FILE, REPORT, COLUMN, API, CODE, GLOSSARY_TERM
            owner_name: Filter by asset owner name
            steward_name: Filter by data steward name
            dq_score_min: Minimum DQ score filter (0-100)
            certification_status: certified / cautioned / violated / inactive
            connection_name: Filter by source connector name
            has_lineage: Filter to assets with lineage mapped
            is_cde: Filter to Critical Data Elements only
            sort_by: RELEVANCE (default), POPULARITY, DQ_SCORE, CURATION_SCORE, NAME
            limit: Max results per page (default 10, max 50)
            offset: Starting position for pagination (default 0)

        TODO: confirm endpoint path from OvalEdge API docs
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.post(
                    "/api/mcp/catalog/search",  # TODO: confirm path
                    body={
                        "keywords": keywords,
                        "objectTypes": object_types,
                        "filters": {
                            "ownerName": owner_name,
                            "stewardName": steward_name,
                            "dqScoreMin": dq_score_min,
                            "certificationStatus": certification_status,
                            "connectionName": connection_name,
                            "hasLineage": has_lineage,
                            "isCde": is_cde,
                        },
                        "sortBy": sort_by,
                        "limit": min(limit, 50),
                        "offset": max(offset, 0),
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool()
    async def get_asset_details(
        object_id: str,
        object_type: str,
        include_columns: bool = False,
        include_sample_values: bool = False,
    ) -> dict[str, Any]:
        """
        Returns complete composite metadata for a single data asset.
        OvalEdge assembles this server-side from multiple internal APIs
        (Object, Column, Business Glossary, DQ Rule, Governance Roles).

        Resolves term-inherited properties — if a column is masked or
        restricted because of a linked glossary term (Glossary-Catalog Sync),
        the response flags is_masked, is_restricted, and mask_source.

        Args:
            object_id: OvalEdge internal object identifier
            object_type: TABLE, FILE, REPORT, COLUMN, FILE_COLUMN,
                         REPORT_COLUMN, API, API_ATTRIBUTE, CODE
            include_columns: Include column-level metadata (tables/files/reports)
            include_sample_values: Include top values per column.
                                   Requires Data Preview permission.

        TODO: confirm endpoint path from OvalEdge API docs
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    f"/api/mcp/assets/{object_id}/composite",  # TODO: confirm path
                    params={
                        "objectType": object_type,
                        "includeColumns": include_columns,
                        "includeSampleValues": include_sample_values,
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool()
    async def count_catalog_assets(
        keywords: list[str] | None = None,
        object_types: list[str] | None = None,
        owner_name: str | None = None,
        dq_score_min: int | None = None,
        certification_status: str | None = None,
        connection_name: str | None = None,
        has_lineage: bool | None = None,
        is_cde: bool | None = None,
    ) -> dict[str, Any]:
        """
        Returns a count of catalog assets matching given filters.
        Does NOT return full result sets — count only.

        Use this for aggregation questions like:
        'How many certified tables exist in the Finance domain?'
        'How many assets have lineage mapped?'

        Prevents unnecessary full searches and avoids the 50-result cap
        when only a count is needed.

        Returns:
            count: total matching assets
            object_types_breakdown: count per object type
            certification_breakdown: count per certification status

        TODO: confirm endpoint path from OvalEdge API docs
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.post(
                    "/api/mcp/catalog/count",  # TODO: confirm path
                    body={
                        "keywords": keywords,
                        "objectTypes": object_types,
                        "filters": {
                            "ownerName": owner_name,
                            "dqScoreMin": dq_score_min,
                            "certificationStatus": certification_status,
                            "connectionName": connection_name,
                            "hasLineage": has_lineage,
                            "isCde": is_cde,
                        },
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
