"""Helpers for MCP tool description text (classification, budget)."""

from __future__ import annotations

from server.constants import (
    MCP_TOOL_CLASSIFICATION_CONFIDENTIAL,
    MCP_TOOL_CLASSIFICATION_INTERNAL,
)


def classify_tool_desc(body: str, *, confidential: bool = False) -> str:
    """Append enterprise data-classification one-liner when not already present."""
    text = body.rstrip()
    if "Data classification:" in text:
        return text
    label = (
        MCP_TOOL_CLASSIFICATION_CONFIDENTIAL
        if confidential
        else MCP_TOOL_CLASSIFICATION_INTERNAL
    )
    return f"{text}\n\n{label}"
