from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import MCP_PATH_GLOSSARY_TERMS, MCP_PATH_TAGS
from server.tools import governance
from tests.conftest import MOCK_GLOSSARY_RESULT
from tests.helpers import get_tool_fn


class TestLookupGlossaryTerm:
    async def test_term_name_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="churn")
        assert out == MOCK_GLOSSARY_RESULT
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            params={"termName": "churn"},
        )

    async def test_rejects_both_id_and_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(object_id=1, term_name="x")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_object_id_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(object_id=99)
        assert out == MOCK_GLOSSARY_RESULT
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            params={"objectId": 99},
        )

    async def test_rejects_neither_id_nor_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_whitespace_term_name_treated_as_missing(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="   ")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="revenue")
        assert out["status_code"] == 403


class TestLookupTags:
    async def test_object_id_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"tag": "t"}
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        await fn(object_id=3)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_TAGS,
            params={"objectId": 3},
        )

    async def test_rejects_both_id_and_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(object_id=1, tag_name="PII")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_neither_id_nor_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(404, "Not found")
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(tag_name="missing")
        assert out["status_code"] == 404
