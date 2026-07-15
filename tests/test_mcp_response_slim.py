"""MCP tool response size / description trimming."""

from __future__ import annotations

import json

from server.mcp_response_slim import (
    MCP_DESCRIPTION_MARKUP_MAX_CHARS,
    MCP_DESCRIPTION_PLAIN_MAX_CHARS,
    MCP_TOOL_RESPONSE_MAX_BYTES,
    slim_tool_response,
)


class TestSlimToolResponse:
    def test_no_op_on_small_payload(self) -> None:
        payload = {"objectId": 1, "name": "t", "description": "short"}
        assert slim_tool_response(payload) == payload

    def test_no_op_on_error_dict(self) -> None:
        err = {"error": "nope", "status_code": 400}
        assert slim_tool_response(err) is err

    def test_truncates_business_description_wiki_object(self) -> None:
        long_plain = "x" * (MCP_DESCRIPTION_PLAIN_MAX_CHARS + 500)
        long_html = "<p>" + "y" * (MCP_DESCRIPTION_MARKUP_MAX_CHARS + 500) + "</p>"
        payload = {
            "businessDescription": {
                "plainText": long_plain,
                "wikitext": long_html,
            }
        }
        out = slim_tool_response(payload)
        bd = out["businessDescription"]
        assert bd["_mcpDescriptionTruncated"] is True
        assert len(bd["plainText"]) < len(long_plain)
        assert len(bd["wikitext"]) < len(long_html)
        assert "truncated" in bd["plainText"]

    def test_truncates_string_description(self) -> None:
        payload = {"description": "z" * (MCP_DESCRIPTION_PLAIN_MAX_CHARS + 100)}
        out = slim_tool_response(payload)
        assert len(out["description"]) < len(payload["description"])

    def test_search_hits_slimmed(self) -> None:
        payload = {
            "items": [
                {
                    "objectId": 1,
                    "businessDescription": {
                        "plainText": "a" * 20_000,
                    },
                }
            ]
        }
        out = slim_tool_response(payload)
        assert out["items"][0]["businessDescription"]["_mcpDescriptionTruncated"] is True

    def test_stays_under_byte_budget_after_aggressive_pass(self) -> None:
        huge = "word " * 300_000
        payload = {"misc": huge, "notes": huge}
        out = slim_tool_response(payload)
        assert _bytes(out) <= MCP_TOOL_RESPONSE_MAX_BYTES + 500

    def test_preserves_formatted_response_under_aggressive_cap(self) -> None:
        # Simulate a metadata-drift narrative that would previously be chopped at 2k
        # before Top row-count adds reached the agent.
        body = (
            "**Summary**\n\n| Metric | Value |\n| --- | --- |\n| Total changes | 369 |\n\n"
            "**Top row-count adds**\n\n"
            "- `oe_internal_diagnostics_delete_query` (+81,708)\n"
            "- `a_dqi_score` (+60,616)\n"
            + ("- filler note about unrelated columns\n" * 80)
        )
        assert len(body) > 2_000
        payload = {
            "ok": True,
            "formattedResponse": body,
            "data": {
                "formattedResponse": body,
                "columnChanges": [{"detail": "x" * 50_000} for _ in range(40)],
            },
        }
        out = slim_tool_response(payload)
        assert "**Top row-count adds**" in out["formattedResponse"]
        assert "`oe_internal_diagnostics_delete_query` (+81,708)" in out["formattedResponse"]
        assert "**Top row-count adds**" in out["data"]["formattedResponse"]


def _bytes(payload: object) -> int:
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
