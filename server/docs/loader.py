"""Load static markdown files as MCP doc resources."""

from __future__ import annotations

import pathlib

from fastmcp import FastMCP

from server.constants import DOCS_RESOURCE_URI_PREFIX

DOCS_DIR = pathlib.Path(__file__).resolve().parent


def read_doc_markdown(stem: str) -> str:
    """Load one markdown file from server/docs/ by stem (filename without .md)."""
    path = DOCS_DIR / f"{stem}.md"
    return path.read_text(encoding="utf-8")


def make_doc_resource(mcp: FastMCP, uri: str, content: str, name: str) -> None:
    """
    Register one markdown file as an MCP resource.

    Uses a factory so each closure captures its own content (not the loop variable).
    """

    @mcp.resource(uri)
    async def _doc() -> str:
        return content

    _doc.__doc__ = f"OvalEdge platform documentation: {name.replace('_', ' ').title()}"


def register_markdown_resources(mcp: FastMCP) -> None:
    """Register all .md files in this directory as MCP doc resources."""
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        doc_name = md_file.stem
        uri = f"{DOCS_RESOURCE_URI_PREFIX}/{doc_name}"
        content = md_file.read_text(encoding="utf-8")
        make_doc_resource(mcp, uri, content, doc_name)
