"""Keep MCP tool descriptions within agent context budget."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

import server.tools
from server.constants import (
    MCP_TOOL_CLASSIFICATION_CONFIDENTIAL,
    MCP_TOOL_CLASSIFICATION_INTERNAL,
)

MCP_TOOL_DESC_MAX_CHARS = 2500
MCP_TOOL_DESC_TOTAL_MAX_CHARS = 32_000


def _collect_tool_descriptions() -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        server.tools.__path__, server.tools.__name__ + "."
    ):
        if "helpers" not in modname:
            continue
        try:
            module = importlib.import_module(modname)
        except Exception:
            continue
        for attr in dir(module):
            if not attr.startswith("_DESC_"):
                continue
            value: Any = getattr(module, attr)
            if isinstance(value, str):
                descriptions[f"{modname}.{attr}"] = value
    return descriptions


class TestToolDescriptionBudget:
    def test_each_tool_description_within_budget(self) -> None:
        descriptions = _collect_tool_descriptions()
        assert descriptions, "expected at least one _DESC_* tool description"
        over: list[str] = []
        for key, text in sorted(descriptions.items()):
            if len(text) > MCP_TOOL_DESC_MAX_CHARS:
                over.append(f"{key}: {len(text)} chars")
        assert not over, "tool descriptions over budget:\n" + "\n".join(over)

    def test_total_tool_description_budget(self) -> None:
        total = sum(len(text) for text in _collect_tool_descriptions().values())
        assert total <= MCP_TOOL_DESC_TOTAL_MAX_CHARS, (
            f"total _DESC_* size {total} exceeds {MCP_TOOL_DESC_TOTAL_MAX_CHARS}"
        )

    def test_all_descriptions_include_data_classification(self) -> None:
        for key, text in _collect_tool_descriptions().items():
            assert "Data classification:" in text, f"missing classification on {key}"

    def test_confidential_classification_on_access_tools(self) -> None:
        from server.tools.access.helpers import _DESC_GET_USER_OBJECT_ACCESS
        from server.tools.rdam.helpers import _DESC_SOURCE_SYSTEM_ACCESS

        assert MCP_TOOL_CLASSIFICATION_CONFIDENTIAL in _DESC_GET_USER_OBJECT_ACCESS
        assert MCP_TOOL_CLASSIFICATION_CONFIDENTIAL in _DESC_SOURCE_SYSTEM_ACCESS

    def test_internal_classification_on_asset_explorer(self) -> None:
        from server.tools.catalog.helpers import _DESC_ASSET_EXPLORER

        assert MCP_TOOL_CLASSIFICATION_INTERNAL in _DESC_ASSET_EXPLORER

    def test_source_system_access_description_is_compact(self) -> None:
        from server.tools.rdam.helpers import _DESC_SOURCE_SYSTEM_ACCESS

        assert len(_DESC_SOURCE_SYSTEM_ACCESS) <= MCP_TOOL_DESC_MAX_CHARS
        assert "docs://ovaledge/rdam_source_access" in _DESC_SOURCE_SYSTEM_ACCESS

    def test_asset_explorer_description_points_to_docs_not_inline_allowlist(self) -> None:
        from server.tools.catalog.helpers import _DESC_ASSET_EXPLORER

        assert "docs://ovaledge/asset_types" in _DESC_ASSET_EXPLORER
        assert "docs://ovaledge/mcp_workflows" in _DESC_ASSET_EXPLORER

    def test_governed_write_descriptions_point_to_docs(self) -> None:
        from server.tools.catalog.helpers import _DESC_UPDATE_DESCRIPTIONS
        from server.tools.governance.glossary_helpers import _DESC_CREATE_GLOSSARY
        from server.tools.governance.tag_helpers import _DESC_CREATE_TAG

        assert "docs://ovaledge/glossary_guide" in _DESC_CREATE_GLOSSARY
        assert "docs://ovaledge/tags_guide" in _DESC_CREATE_TAG
        assert "docs://ovaledge/mcp_workflows" in _DESC_UPDATE_DESCRIPTIONS
        assert len(_DESC_CREATE_GLOSSARY) <= MCP_TOOL_DESC_MAX_CHARS
        assert len(_DESC_CREATE_TAG) <= MCP_TOOL_DESC_MAX_CHARS
        assert len(_DESC_UPDATE_DESCRIPTIONS) <= MCP_TOOL_DESC_MAX_CHARS
