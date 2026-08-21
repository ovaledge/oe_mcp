"""Shared markdown/cell formatting for MCP tool responses."""

from __future__ import annotations


def cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()
