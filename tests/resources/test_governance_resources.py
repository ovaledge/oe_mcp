import json

from fastmcp import FastMCP

from server.constants import MCP_PATH_OBJECT_DETAILS, MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM
from server.resources import governance as governance_res


class TestGovernanceResources:
    async def test_glossary_term_resource(self, mock_oe_client: object) -> None:
        payload = {"objectId": 7, "objectType": "glossary", "name": "Revenue"}
        mock_oe_client.get.return_value = payload
        mcp = FastMCP(name="test", version="0.0.1")
        governance_res.register(mcp)
        tmpl = await mcp.get_resource_template(MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM)
        assert tmpl is not None
        text = await tmpl.fn("7")
        assert json.loads(text) == payload
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_OBJECT_DETAILS,
            params={"objectId": 7, "objectType": "glossary"},
        )
