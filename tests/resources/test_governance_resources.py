import json
from unittest.mock import AsyncMock

from fastmcp import FastMCP
from fastmcp.resources.template import FunctionResourceTemplate

from server.constants import (
    MCP_PATH_ASSET_DETAILS,
    MCP_RESOURCE_GOVERNANCE_DATA_STORY,
    MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM,
    MCP_RESOURCE_GOVERNANCE_TAG,
)
from server.resources import governance as governance_res


class TestGovernanceResources:
    async def test_glossary_term_resource(self, mock_oe_client: AsyncMock) -> None:
        payload = {"objectId": 7, "objectType": "glossary", "name": "Revenue"}
        mock_oe_client.get.return_value = payload
        mcp = FastMCP(name="test", version="0.0.1")
        governance_res.register(mcp)
        tmpl = await mcp.get_resource_template(MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM)
        assert tmpl is not None
        assert isinstance(tmpl, FunctionResourceTemplate)
        text = await tmpl.fn("7")
        assert json.loads(text) == payload
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ASSET_DETAILS,
            params={"objectId": 7, "objectType": "glossary"},
        )

    async def test_data_story_resource(self, mock_oe_client: AsyncMock) -> None:
        payload = {"objectId": 99, "objectType": "oestory", "name": "Onboarding"}
        mock_oe_client.get.return_value = payload
        mcp = FastMCP(name="test", version="0.0.1")
        governance_res.register(mcp)
        tmpl = await mcp.get_resource_template(MCP_RESOURCE_GOVERNANCE_DATA_STORY)
        assert tmpl is not None
        text = await tmpl.fn("99")
        assert json.loads(text) == payload
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ASSET_DETAILS,
            params={"objectId": 99, "objectType": "oestory"},
        )

    async def test_tag_resource(self, mock_oe_client: AsyncMock) -> None:
        payload = {"objectId": 12, "objectType": "oetag", "name": "PII"}
        mock_oe_client.get.return_value = payload
        mcp = FastMCP(name="test", version="0.0.1")
        governance_res.register(mcp)
        tmpl = await mcp.get_resource_template(MCP_RESOURCE_GOVERNANCE_TAG)
        assert tmpl is not None
        text = await tmpl.fn("12")
        assert json.loads(text) == payload
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ASSET_DETAILS,
            params={"objectId": 12, "objectType": "oetag"},
        )
