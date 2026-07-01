from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_PATH_LOOKUP_DQ_RULES,
)
from server.tools import dataquality
from tests.helpers import get_tool_fn


class TestLookupDqRule:
    async def test_rule_name_lookup(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": [
                {
                    "objectId": 42,
                    "objectType": "dqrule",
                    "objectName": "Null Data Density Check",
                }
            ],
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_dq_rule")
        out = await fn(rule_name="Null Data Density")
        assert out["ok"] is True
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DQ_RULES,
            params={"ruleName": "Null Data Density", "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT},
        )

    async def test_rejects_both_id_and_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_dq_rule")
        out = await fn(object_id=1, rule_name="x")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(404, "Rule not found")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_dq_rule")
        out = await fn(rule_name="missing-rule")
        assert out["status_code"] == 404
        assert "404" in out["error"]
