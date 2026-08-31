"""Unit tests for RDAM catalog identifier resolve (asset_explorer → DAM)."""

from unittest.mock import AsyncMock

from server.constants import MCP_PATH_ASSET_EXPLORER
from server.tools.rdam.catalog_resolve import (
    catalog_object_type_for_explorer,
    rdam_object_type_from_catalog,
    resolve_rdam_scope_via_asset_explorer,
    should_resolve_via_asset_explorer,
)


class TestShouldResolveViaAssetExplorer:
    def test_skips_when_object_id_and_type_are_known(self) -> None:
        assert (
            should_resolve_via_asset_explorer(
                "object_to_users",
                42,
                "table",
                "prod.public.orders",
                None,
                None,
            )
            is False
        )

    def test_resolves_named_fqn_without_object_id(self) -> None:
        assert (
            should_resolve_via_asset_explorer(
                "object_to_users",
                None,
                "schema",
                None,
                None,
                "SUPERSTORE.SUPERSTORE",
            )
            is True
        )

    def test_skips_browse_parent_path_resolution(self) -> None:
        assert (
            should_resolve_via_asset_explorer(
                "browse",
                None,
                "table",
                "BUSINESS.BANKING",
                None,
                None,
            )
            is False
        )

    def test_skips_membership_direction_resolution(self) -> None:
        assert (
            should_resolve_via_asset_explorer(
                "role_to_users",
                None,
                None,
                "SYSADMIN",
                None,
                None,
            )
            is False
        )
        assert (
            should_resolve_via_asset_explorer(
                "group_to_users",
                None,
                None,
                "analysts",
                None,
                None,
            )
            is False
        )
        assert (
            should_resolve_via_asset_explorer(
                "user_to_roles",
                None,
                None,
                None,
                None,
                None,
            )
            is False
        )


class TestCatalogTypeMapping:
    def test_catalog_object_type_for_explorer_maps_rdam(self) -> None:
        assert catalog_object_type_for_explorer("table") == "oetable"
        assert catalog_object_type_for_explorer("oeschema") == "oeschema"

    def test_rdam_object_type_from_catalog(self) -> None:
        assert rdam_object_type_from_catalog("oetable") == "table"
        assert rdam_object_type_from_catalog("schema") == "schema"


class TestResolveRdamScopeViaAssetExplorer:
    async def test_resolves_hit_on_matching_connection_id(self) -> None:
        client = AsyncMock()
        client.post.return_value = {
            "ok": True,
            "data": {
                "items": [
                    {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod_db.public.orders",
                        "connectionInfoId": 1000,
                    }
                ]
            },
        }
        client.get.side_effect = [
            {
                "ok": True,
                "data": {
                    "details": {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod_db.public.orders",
                        "connectionInfoId": 1000,
                    }
                },
            },
        ]

        resolved = await resolve_rdam_scope_via_asset_explorer(
            client,
            source_system="redshift",
            object_id=None,
            object_type="table",
            object_name=None,
            fully_qualified_name=None,
            resolve_all_matches=False,
            connection_id=1000,
            object_path="prod_db.public.orders",
        )

        assert resolved is not None
        assert resolved.connection_id == 1000
        assert resolved.object_id == 42
        client.post.assert_awaited()
        posted = client.post.await_args
        assert posted.args[0] == MCP_PATH_ASSET_EXPLORER
        body = posted.kwargs["body"]
        assert body["filters"]["serverType"] == "redshift"
        assert isinstance(body["filters"]["serverType"], str)

    async def test_mismatched_connection_id_returns_none(self) -> None:
        client = AsyncMock()
        client.post.return_value = {
            "ok": True,
            "data": {
                "items": [
                    {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod_db.public.orders",
                        "connectionInfoId": 2000,
                    }
                ]
            },
        }

        resolved = await resolve_rdam_scope_via_asset_explorer(
            client,
            source_system="redshift",
            object_id=None,
            object_type="table",
            object_name=None,
            fully_qualified_name=None,
            resolve_all_matches=False,
            connection_id=1000,
            object_path="prod_db.public.orders",
        )

        assert resolved is None

    async def test_unknown_connection_id_keeps_caller_connection(self) -> None:
        client = AsyncMock()
        client.post.return_value = {
            "ok": True,
            "data": {
                "items": [
                    {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod_db.public.orders",
                    }
                ]
            },
        }
        client.get.side_effect = [
            {
                "ok": True,
                "data": {
                    "details": {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod_db.public.orders",
                    }
                },
            },
        ]

        resolved = await resolve_rdam_scope_via_asset_explorer(
            client,
            source_system="redshift",
            object_id=None,
            object_type="table",
            object_name=None,
            fully_qualified_name=None,
            resolve_all_matches=False,
            connection_id=1000,
            object_path="prod_db.public.orders",
        )

        assert resolved is not None
        assert resolved.connection_id == 1000
        assert resolved.object_id == 42

    async def test_multi_match_filters_to_connection_id(self) -> None:
        client = AsyncMock()
        client.post.return_value = {
            "ok": True,
            "data": {
                "items": [
                    {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod.public.orders",
                        "connectionInfoId": 2000,
                    },
                    {
                        "objectId": 84,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod.public.orders_archive",
                        "connectionInfoId": 3000,
                    },
                ]
            },
        }
        client.get.side_effect = [
            {
                "ok": True,
                "data": {
                    "details": {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod.public.orders",
                        "connectionInfoId": 2000,
                    }
                },
            },
        ]

        resolved = await resolve_rdam_scope_via_asset_explorer(
            client,
            source_system="redshift",
            object_id=None,
            object_type="table",
            object_name=None,
            fully_qualified_name=None,
            resolve_all_matches=False,
            connection_id=2000,
            object_path="orders",
        )

        assert resolved is not None
        assert resolved.connection_id == 2000
        assert resolved.object_path == "prod.public.orders"
        assert resolved.object_id == 42

    async def test_multi_match_drops_connection_id_when_hits_span_connectors(self) -> None:
        client = AsyncMock()
        client.post.return_value = {
            "ok": True,
            "data": {
                "items": [
                    {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod.public.orders",
                        "connectionInfoId": 2000,
                    },
                    {
                        "objectId": 84,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod.public.orders_archive",
                        "connectionInfoId": 3000,
                    },
                ]
            },
        }
        client.get.side_effect = [
            {
                "ok": True,
                "data": {
                    "details": {
                        "objectId": 42,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod.public.orders",
                        "connectionInfoId": 2000,
                    }
                },
            },
            {
                "ok": True,
                "data": {
                    "details": {
                        "objectId": 84,
                        "objectType": "oetable",
                        "fullyQualifiedName": "prod.public.orders_archive",
                        "connectionInfoId": 3000,
                    }
                },
            },
        ]

        resolved = await resolve_rdam_scope_via_asset_explorer(
            client,
            source_system="redshift",
            object_id=None,
            object_type="table",
            object_name=None,
            fully_qualified_name=None,
            resolve_all_matches=True,
            connection_id=None,
            object_path="orders",
        )

        assert resolved is not None
        assert resolved.object_path == [
            "prod.public.orders",
            "prod.public.orders_archive",
        ]
        assert resolved.connection_id is None
