"""Keep MCP tool JSON responses under client size limits (e.g. Cursor ~1MB)."""

from __future__ import annotations

import copy
import json
from typing import Any

# Stay under Cursor's ~1MB tool-result cap (JSON serialization adds overhead).
MCP_TOOL_RESPONSE_MAX_BYTES = 900_000
MCP_DESCRIPTION_PLAIN_MAX_CHARS = 6_000
MCP_DESCRIPTION_MARKUP_MAX_CHARS = 1_500

# OvalEdge wiki-style description objects (businessDescription, etc.).
_DESCRIPTION_OBJECT_KEYS = frozenset(
    {
        "businessdescription",
        "technicaldescription",
        "detaileddescription",
        "domaindescription",
        "tagdescription",
        "mastertagdescription",
    }
)

_PLAIN_TEXT_KEYS = ("plainText", "wikitextplain", "wikiTextPlain", "plain_text")
_MARKUP_TEXT_KEYS = ("wikitext", "wikiText", "html", "techtext", "techText", "richText")

_STRING_DESCRIPTION_KEYS = frozenset(
    {
        "description",
        "definition",
        "businessdescription",
        "technicaldescription",
        "detaileddescription",
        "domaindescription",
        "tagdescription",
        "mastertagdescription",
        "sourcedescription",
        "storycontent",
        "content",
    }
)


def _truncate_text(text: str, max_chars: int, label: str) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    omitted = len(text) - max_chars
    return (
        text[:max_chars]
        + f"\n\n...[truncated {label}: {omitted:,} more characters; "
        "use a narrower tool or OvalEdge UI for full text]",
        True,
    )


def _slim_wiki_object(obj: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    for key in _PLAIN_TEXT_KEYS:
        val = obj.get(key)
        if isinstance(val, str):
            new, did = _truncate_text(val, MCP_DESCRIPTION_PLAIN_MAX_CHARS, key)
            if did:
                obj[key] = new
                changed = True
    for key in _MARKUP_TEXT_KEYS:
        val = obj.get(key)
        if isinstance(val, str):
            new, did = _truncate_text(val, MCP_DESCRIPTION_MARKUP_MAX_CHARS, key)
            if did:
                obj[key] = new
                changed = True
    if changed:
        obj["_mcpDescriptionTruncated"] = True
    return obj, changed


def _slim_inplace(node: Any) -> bool:
    """Recursively trim description fields. Returns True if anything changed."""
    changed = False
    if isinstance(node, dict):
        for key, value in list(node.items()):
            key_lower = str(key).lower()
            if isinstance(value, dict) and key_lower in _DESCRIPTION_OBJECT_KEYS:
                _, did = _slim_wiki_object(value)
                changed = changed or did
            elif isinstance(value, str) and key_lower in _STRING_DESCRIPTION_KEYS:
                new, did = _truncate_text(value, MCP_DESCRIPTION_PLAIN_MAX_CHARS, key)
                if did:
                    node[key] = new
                    changed = True
            elif isinstance(value, (dict, list)):
                if _slim_inplace(value):
                    changed = True
    elif isinstance(node, list):
        for item in node:
            if _slim_inplace(item):
                changed = True
    return changed


def _aggressive_string_cap(node: Any, max_chars: int = 2_000) -> None:
    """Last resort: cap any remaining long strings before returning to MCP clients."""
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if isinstance(value, str) and len(value) > max_chars:
                node[key], _ = _truncate_text(value, max_chars, str(key))
                node["_mcpResponseTruncated"] = True
            elif isinstance(value, (dict, list)):
                _aggressive_string_cap(value, max_chars)
    elif isinstance(node, list):
        for item in node:
            _aggressive_string_cap(item, max_chars)


def _payload_bytes(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


def slim_tool_response(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Trim oversized description / wiki fields on tool responses.

    Mutates a deep copy only. Error dicts (error + status_code) are returned unchanged.
    """
    if "error" in payload and "status_code" in payload:
        return payload

    out: dict[str, Any] = copy.deepcopy(payload)
    _slim_inplace(out)

    if _payload_bytes(out) > MCP_TOOL_RESPONSE_MAX_BYTES:
        _aggressive_string_cap(out)
        if _payload_bytes(out) > MCP_TOOL_RESPONSE_MAX_BYTES:
            out["_mcpResponseNote"] = (
                "Response still exceeds MCP client size limits after truncation. "
                "Retry with search_catalog_assets (smaller limit), fewer assets, "
                "or read descriptions in OvalEdge UI."
            )
    return out
