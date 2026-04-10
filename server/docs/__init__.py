import pathlib

from fastmcp import FastMCP

DOCS_DIR = pathlib.Path(__file__).parent


def _make_doc_resource(mcp: FastMCP, uri: str, content: str, name: str) -> None:
    """
    Factory function that creates a doc resource with properly captured content.
    Avoids the closure-in-a-loop bug where all resources return the last file's content.
    """

    @mcp.resource(uri)
    async def _doc() -> str:
        return content

    _doc.__doc__ = f"OvalEdge platform documentation: {name.replace('_', ' ').title()}"


def register(mcp: FastMCP) -> None:
    """Auto-register all .md files in this directory as MCP doc resources."""
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        doc_name = md_file.stem
        uri = f"docs://ovaledge/{doc_name}"
        content = md_file.read_text(encoding="utf-8")
        _make_doc_resource(mcp, uri, content, doc_name)
