"""Tests for MCP response slimming (client 1 MB limit)."""

from __future__ import annotations

import json

from server.mcp_response_slim import slim_mcp_tool_payload


def test_truncates_business_description_text() -> None:
    huge = "x" * 20_000
    payload = {
        "ok": True,
        "data": {
            "objectName": "version",
            "businessDescription": {"text": huge, "html": "<p>" + "y" * 5000 + "</p>"},
        },
    }
    out = slim_mcp_tool_payload(payload)
    text = out["data"]["businessDescription"]["text"]
    assert len(text) < 7000
    assert "truncated" in text
    assert out["_mcpDescriptionTruncated"] is True
    assert "_mcpResponseNote" in out


def test_truncates_search_hit_description_snippet() -> None:
    payload = {
        "ok": True,
        "items": [{"objectName": "t", "description": "z" * 2000}],
    }
    out = slim_mcp_tool_payload(payload)
    assert len(out["items"][0]["description"]) < 600
    assert out["_mcpDescriptionTruncated"] is True


def test_skips_error_payloads() -> None:
    payload = {"error": "bad", "status_code": 400}
    assert slim_mcp_tool_payload(payload) is payload


def test_whole_payload_cap() -> None:
    payload = {"ok": True, "rows": [{"note": "a" * 50_000} for _ in range(30)]}
    out = slim_mcp_tool_payload(payload)
    assert len(json.dumps(out, ensure_ascii=False).encode()) < 950_000


def test_caps_large_attributes_array() -> None:
    cols = [{"objectName": f"col_{i}", "description": "x" * 100} for i in range(120)]
    payload = {
        "ok": True,
        "data": {"objectName": "big_table", "columnCount": 120, "attributes": cols},
    }
    out = slim_mcp_tool_payload(payload)
    assert len(out["data"]["attributes"]) == 50
    assert out["data"]["_mcpColumnsTruncated"]["total"] == 120
    assert "Column arrays capped" in out["_mcpResponseNote"]
