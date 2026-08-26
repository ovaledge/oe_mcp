"""Static markdown doc resources under server/docs/."""

from __future__ import annotations

import re
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.client import Client

from server.constants import DOCS_RESOURCE_URI_PREFIX, MCP_ASSET_EXPLORER_FILTER_KEYS
from server.docs.loader import DOCS_DIR, read_doc_markdown
from server.docs.register import register as register_doc_resources
from server.mcp_surface import MCP_TOOL_NAMES, MCP_WORKFLOW_PROMPT_NAMES

SERVER_DIR = Path(__file__).resolve().parents[2] / "server"
_DOCS_URI_RE = re.compile(re.escape(DOCS_RESOURCE_URI_PREFIX) + r"/([a-z0-9_]+)")


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
        assert "governance" in {f.stem for f in md_files}
        assert "asset_types" in {f.stem for f in md_files}
        assert "rdam_source_access" in {f.stem for f in md_files}
        assert "overview" in {f.stem for f in md_files}
        # Merged guides (must not reappear as separate stems)
        assert "glossary_guide" not in {f.stem for f in md_files}
        assert "tags_guide" not in {f.stem for f in md_files}
        assert "data_stories" not in {f.stem for f in md_files}
        assert "governance_model" not in {f.stem for f in md_files}

    def test_every_referenced_docs_uri_resolves_to_a_doc(self) -> None:
        """No tool description, prompt, or doc may point at a docs:// stem that is gone."""
        stems = {f.stem for f in DOCS_DIR.glob("*.md")}
        dangling: dict[str, set[str]] = {}
        sources = list(SERVER_DIR.rglob("*.py")) + list(SERVER_DIR.rglob("*.md"))
        for path in sources:
            if "__pycache__" in path.parts:
                continue
            for stem in set(_DOCS_URI_RE.findall(path.read_text(encoding="utf-8"))):
                if stem not in stems:
                    rel = path.relative_to(SERVER_DIR.parent).as_posix()
                    dangling.setdefault(stem, set()).add(rel)
        assert not dangling, (
            "docs:// references with no matching server/docs/*.md: "
            + "; ".join(f"{stem} ← {sorted(files)}" for stem, files in sorted(dangling.items()))
        )

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
        assert "knowledge_search" in text
        assert "organizational_knowledge" in text
        assert "Native source access (RDAM)" in text
        assert "user_to_objects" in text
        assert "source_system_access" in text
        assert "Catalog object access" in text
        assert "Update asset descriptions" in text
        assert "dp_domain" in text

    def test_mcp_workflows_documents_registered_surface(self) -> None:
        """Routing guide must list every tool and workflow prompt from mcp_surface."""
        text = read_doc_markdown("mcp_workflows")
        missing_tools = sorted(name for name in MCP_TOOL_NAMES if f"`{name}`" not in text)
        missing_prompts = sorted(
            name for name in MCP_WORKFLOW_PROMPT_NAMES if f"`{name}`" not in text
        )
        assert not missing_tools, f"mcp_workflows.md missing tools: {missing_tools}"
        assert not missing_prompts, f"mcp_workflows.md missing prompts: {missing_prompts}"

    def test_mcp_workflows_routes_first_person_inventory_to_asset_explorer(self) -> None:
        text = read_doc_markdown("mcp_workflows")
        assert "Discovery vs grants" in text
        assert "What tables/schemas/columns can I see/view/access?" in text
        assert "without a named principal" in text
        assert "First-person **with** a named source" in text

    def test_mcp_workflows_range_filters_are_open_ended(self) -> None:
        text = read_doc_markdown("mcp_workflows")
        compact = text.replace(" ", "")
        assert "filters={\"rating\":{\"min\":4}}" in compact
        assert "filters={\"rating\":{\"min\":4.01}}" in compact
        assert "filters={\"rating\":{\"max\":3}}" in compact
        assert "filters={\"popularity\":{\"min\":70}}" in compact
        created = "filters={\"createdDate\":{\"from\":\"2024-01-01\",\"to\":\"2024-12-31\"}}"
        assert created in compact
        assert "`createdDate` uses `{from,to}` ISO dates, not min/max" in text
        assert "Do not invent `max:5`" in text
        assert "Omit any bound the user did not specify" in text
        assert "this tool always sends `search.page` and `search.limit`" in text
        assert "Backend: **POST** `/api/v1/mcp/asset-explorer`" in text
        assert "GET `/api/v1/mcp/asset-explorer`" not in text
        extra_facets = MCP_ASSET_EXPLORER_FILTER_KEYS - {
            "connectionName",
            "serverType",
            "schemaName",
            "owner",
            "steward",
            "custodian",
            "tags",
            "terms",
            "customFields",
            "dataProducts",
            "classifications",
            "criticalDataElement",
        }
        for key in extra_facets:
            assert key in text, f"mcp_workflows missing nested filter key {key}"
