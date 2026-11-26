"""ai_asset_details forwards AI Governance lookups to the Elasticsearch-backed API."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import MCP_PATH_AI_ASSET_DETAILS, TOOL_AI_ASSET_DETAILS
from server.tools.catalog import register as register_catalog
from server.tools.catalog.helpers import _DESC_AI_ASSET_DETAILS
from tests.helpers import get_tool_fn


class TestAiAssetDetails:
    async def test_forwards_canonical_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "objectId": 12,
                "objectType": "aig_models",
                "assetName": "Credit Model",
                "navLink": "#nav/aig_models?id=12",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        register_catalog(mcp)
        fn = await get_tool_fn(mcp, TOOL_AI_ASSET_DETAILS)
        out = await fn(object_id=12, object_type="ai model")
        assert mock_oe_client.get.call_args[0][0] == MCP_PATH_AI_ASSET_DETAILS
        assert mock_oe_client.get.call_args[1]["params"] == {
            "objectId": 12,
            "objectType": "aig_models",
        }
        assert out["data"]["redirectUrl"].endswith("#nav/aig_models?id=12")

    async def test_rejects_catalog_type_without_calling_api(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_catalog(mcp)
        fn = await get_tool_fn(mcp, TOOL_AI_ASSET_DETAILS)
        result = await fn(object_id=1, object_type="oetable")
        assert result["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_non_positive_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_catalog(mcp)
        fn = await get_tool_fn(mcp, TOOL_AI_ASSET_DETAILS)
        result = await fn(object_id=0, object_type="aig_agents")
        assert result["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    def test_description_routes_away_from_catalog_details(self) -> None:
        assert "ai_asset_details" in _DESC_AI_ASSET_DETAILS
        assert "asset_details" in _DESC_AI_ASSET_DETAILS
        assert "aig_models" in _DESC_AI_ASSET_DETAILS
        assert MCP_PATH_AI_ASSET_DETAILS in _DESC_AI_ASSET_DETAILS
