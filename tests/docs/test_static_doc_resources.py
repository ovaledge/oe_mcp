"""Static markdown doc resources under server/docs/."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.client import Client

from server.constants import DOCS_RESOURCE_URI_PREFIX
from server.docs.loader import DOCS_DIR
from server.docs.register import register as register_doc_resources


class TestStaticDocResources:
    async def test_every_markdown_file_has_docs_resource(self) -> None:
        md_files = sorted(DOCS_DIR.glob("*.md"))
        assert md_files, "server/docs should contain at least one .md file"
        expected_uris = {f"{DOCS_RESOURCE_URI_PREFIX}/{f.stem}" for f in md_files}

        mcp = FastMCP(name="test", version="0.0.1")
        register_doc_resources(mcp)
        async with Client(mcp) as client:
            listed = await client.list_resources()
        listed_uris = {
            str(r.uri)
            for r in listed
            if str(r.uri).startswith(DOCS_RESOURCE_URI_PREFIX)
        }

        assert expected_uris <= listed_uris
        assert "mcp_workflows" in {f.stem for f in md_files}
        assert "data_stories" in {f.stem for f in md_files}
        assert "tags_guide" in {f.stem for f in md_files}

    async def test_read_mcp_workflows_resource(self) -> None:
        path = DOCS_DIR / "mcp_workflows.md"
        assert path.is_file()
        mcp = FastMCP(name="test", version="0.0.1")
        register_doc_resources(mcp)
        uri = f"{DOCS_RESOURCE_URI_PREFIX}/mcp_workflows"
        async with Client(mcp) as client:
            contents = await client.read_resource(uri)
        assert contents
        text = contents[0].text if hasattr(contents[0], "text") else str(contents[0])
        assert "lookup_datastory" in text
        assert "organizational_knowledge" in text
        assert "Native source access (RDAM)" in text
        assert "user_to_objects" in text
        assert "source_system_access" in text
