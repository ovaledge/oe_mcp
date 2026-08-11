"""Tests for access response enrichment."""

from server.tools.access.helpers import enrich_get_user_object_access_response


class TestEnrichGetUserObjectAccessResponse:
    def test_oestory_inherited_from_adds_advisory(self) -> None:
        result = {
            "ok": True,
            "data": {
                "objectType": "oestory",
                "objectId": 42,
                "inheritedFrom": {
                    "objectId": 1004,
                    "objectType": "storyzone",
                    "objectName": "OvalEdge",
                },
            },
        }
        out = enrich_get_user_object_access_response(result)
        msg = out["data"]["advisoryMessage"]
        assert "inherited from Story Zone" in msg
        assert "OvalEdge" in msg
        assert "no direct catalog permissions" in msg

    def test_non_oestory_unchanged(self) -> None:
        result = {
            "ok": True,
            "data": {
                "objectType": "dp_domain",
                "objectId": 1028,
            },
        }
        out = enrich_get_user_object_access_response(result)
        assert "advisoryMessage" not in out["data"]
