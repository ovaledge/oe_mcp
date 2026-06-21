"""
Trim large description fields and cap whole MCP tool payloads for client limits (~1 MB).

Applied on read paths (catalog details/search, glossary lookup, MCP resources) before
returning JSON to the agent.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

# Cursor and similar clients reject tool results above ~1 MB.
_WHOLE_PAYLOAD_MAX_BYTES = 900_000
_PLAIN_TEXT_MAX = 6_000
_WIKI_HTML_MAX = 1_500
_SEARCH_SNIPPET_MAX = 500
_AGGRESSIVE_STRING_MAX = 2_000
_MAX_COLUMN_ARRAY_ITEMS = 50
_COLUMN_ARRAY_KEYS = frozenset(
    {"attributes", "columns", "fileColumns", "relatedColumns", "childObjects"}
)

_DESCRIPTION_OBJECT_KEYS = frozenset(
    {
        "businessDescription",
        "technicalDescription",
        "sourceDescription",
        "objectDescription",
    }
)
_WIKI_TEXT_KEYS = frozenset({"text", "plainText", "html", "markup"})


def _truncate_str(value: str, max_len: int, *, field_label: str) -> tuple[str, bool]:
    if len(value) <= max_len:
        return value, False
    note = f"… [{field_label} truncated for MCP client size; open in OvalEdge for full text]"
    keep = max(0, max_len - len(note))
    return value[:keep] + note, True


def _slim_wiki_object(obj: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    out = dict(obj)
    truncated = False
    for key in _WIKI_TEXT_KEYS:
        val = out.get(key)
        if not isinstance(val, str):
            continue
        cap = _WIKI_HTML_MAX if key in ("html", "markup") else _PLAIN_TEXT_MAX
        new_val, did = _truncate_str(val, cap, field_label=key)
        if did:
            out[key] = new_val
            truncated = True
    return out, truncated


def _slim_description_value(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        new_val, did = _truncate_str(value, _PLAIN_TEXT_MAX, field_label="description")
        return new_val, did
    if isinstance(value, dict):
        return _slim_wiki_object(value)
    return value, False


def _slim_column_arrays(node: Any) -> tuple[Any, bool]:
    """Cap large column/attribute arrays on catalog detail documents."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        any_truncated = False
        for key, val in node.items():
            if (
                key in _COLUMN_ARRAY_KEYS
                and isinstance(val, list)
                and len(val) > _MAX_COLUMN_ARRAY_ITEMS
            ):
                out[key] = val[:_MAX_COLUMN_ARRAY_ITEMS]
                out["_mcpColumnsTruncated"] = {
                    "field": key,
                    "total": len(val),
                    "returned": _MAX_COLUMN_ARRAY_ITEMS,
                }
                any_truncated = True
            else:
                slimmed, did = _slim_column_arrays(val)
                out[key] = slimmed
                any_truncated = any_truncated or did
        return out, any_truncated
    if isinstance(node, list):
        out_list: list[Any] = []
        any_truncated = False
        for item in node:
            slimmed, did = _slim_column_arrays(item)
            out_list.append(slimmed)
            any_truncated = any_truncated or did
        return out_list, any_truncated
    return node, False


def slim_description_fields(node: Any) -> tuple[Any, bool]:
    """Recursively trim known heavy description keys; return (node, any_truncated)."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        any_truncated = False
        for key, val in node.items():
            if key in _DESCRIPTION_OBJECT_KEYS:
                slimmed, did = _slim_description_value(val)
                out[key] = slimmed
                any_truncated = any_truncated or did
            elif key == "description" and isinstance(val, str):
                slimmed, did = _truncate_str(val, _SEARCH_SNIPPET_MAX, field_label="description")
                out[key] = slimmed
                any_truncated = any_truncated or did
            elif key in ("definition", "detailedDescription") and isinstance(val, str):
                slimmed, did = _truncate_str(val, _PLAIN_TEXT_MAX, field_label=key)
                out[key] = slimmed
                any_truncated = any_truncated or did
            else:
                slimmed, did = slim_description_fields(val)
                out[key] = slimmed
                any_truncated = any_truncated or did
        return out, any_truncated
    if isinstance(node, list):
        out_list: list[Any] = []
        any_truncated = False
        for item in node:
            slimmed, did = slim_description_fields(item)
            out_list.append(slimmed)
            any_truncated = any_truncated or did
        return out_list, any_truncated
    return node, False


def _cap_whole_payload(node: Any) -> tuple[Any, bool]:
    """If JSON still exceeds budget, truncate longest strings aggressively."""
    encoded = json.dumps(node, ensure_ascii=False).encode("utf-8")
    if len(encoded) <= _WHOLE_PAYLOAD_MAX_BYTES:
        return node, False

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        if isinstance(obj, str) and len(obj) > _AGGRESSIVE_STRING_MAX:
            trimmed, _ = _truncate_str(obj, _AGGRESSIVE_STRING_MAX, field_label="field")
            return trimmed
        return obj

    return _walk(deepcopy(node)), True


def slim_mcp_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe for MCP clients; set flags when trimming occurred."""
    if not isinstance(payload, dict):
        return payload
    if payload.get("error") or payload.get("ok") is False:
        return payload

    slimmed, desc_truncated = slim_description_fields(deepcopy(payload))
    slimmed, columns_truncated = _slim_column_arrays(slimmed)
    slimmed, payload_truncated = _cap_whole_payload(slimmed)

    if desc_truncated or columns_truncated or payload_truncated:
        note_parts = []
        if desc_truncated:
            note_parts.append("Long descriptions were shortened")
        if columns_truncated:
            note_parts.append(
                f"Column arrays capped at {_MAX_COLUMN_ARRAY_ITEMS} items"
            )
        if payload_truncated:
            note_parts.append("Overall payload was capped")
        slimmed["_mcpDescriptionTruncated"] = desc_truncated or columns_truncated
        slimmed["_mcpResponseNote"] = (
            "; ".join(note_parts) + ". Use navLink/redirectUrl in OvalEdge for full content."
        )
    return slimmed
