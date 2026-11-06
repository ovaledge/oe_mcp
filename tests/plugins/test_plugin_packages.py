"""Plugin package manifests stay parseable and point at expected paths."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(rel: str) -> dict:
    path = REPO_ROOT / rel
    assert path.is_file(), f"missing {rel}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_claude_plugin_manifest_and_mcp_url_template() -> None:
    plugin = _load("plugins/claude-ovaledge/.claude-plugin/plugin.json")
    assert plugin["name"] == "ovaledge"
    assert "mcp_url" in plugin["userConfig"]
    mcp = _load("plugins/claude-ovaledge/.mcp.json")
    server = mcp["mcpServers"]["ovaledge"]
    assert server["type"] == "http"
    assert "${user_config.mcp_url}" in server["url"]
    skill = REPO_ROOT / "plugins/claude-ovaledge/skills/ovaledge-mcp-workflows/SKILL.md"
    assert skill.is_file()
    assert "docs://ovaledge/mcp_workflows" in skill.read_text(encoding="utf-8")


def test_codex_plugin_manifest_uses_streamable_http_placeholder() -> None:
    plugin = _load("plugins/codex-ovaledge/plugin.json")
    assert plugin["name"] == "ovaledge"
    mcp = _load("plugins/codex-ovaledge/mcp.json")
    server = mcp["mcpServers"]["ovaledge"]
    assert server["type"] == "streamable-http"
    assert server["url"].endswith("/mcp")
    assert "YOUR_PUBLIC_MCP_BASE_URL" in server["url"]


def test_repo_marketplaces_point_at_plugin_packages() -> None:
    claude = _load(".claude-plugin/marketplace.json")
    assert claude["plugins"][0]["source"] == "./plugins/claude-ovaledge"
    agents = _load(".agents/plugins/marketplace.json")
    assert agents["plugins"][0]["source"]["path"] == "./plugins/codex-ovaledge"
