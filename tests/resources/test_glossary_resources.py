import json

from fastmcp import FastMCP

from server.resources import glossary as glossary_res


class TestGlossaryResources:
    async def test_term_resource(self, mock_oe_client: object) -> None:
        payload = {"termId": "t1", "name": "Revenue"}
        mock_oe_client.get.return_value = payload
        mcp = FastMCP(name="test", version="0.0.1")
        glossary_res.register(mcp)
        tmpl = await mcp.get_resource_template("ovaledge://glossary/term/{term_id}")
        assert tmpl is not None
        text = await tmpl.fn("t1")
        assert json.loads(text) == payload
