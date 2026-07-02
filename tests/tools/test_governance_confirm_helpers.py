"""Unit tests for create confirmation preview helpers."""

from __future__ import annotations

from server.tools.governance import helpers as governance_helpers


class TestGlossaryCreateConfirmationPreview:
    def test_preview_blocks_create_and_lists_placement(self) -> None:
        out = governance_helpers._format_glossary_create_confirmation_preview(
            term_name="Revenue",
            domain_id=12,
            domain_name="Finance",
            category_id=55,
            category_name="cost",
            subcategory_id=None,
            subcategory_name=None,
            description="ASC 606 policy.",
            definition=None,
            publish=False,
            post_body={
                "termName": "Revenue",
                "domainId": 12,
                "description": "ASC 606 policy.",
                "category1Id": 55,
                "category2Id": 0,
                "publish": False,
            },
        )
        assert out["ok"] is True
        assert out["workflowPhase"] == "confirm_create"
        assert out["doNotCreate"] is True
        assert out["writeConfirmedByUser"] is False
        assert "confirmationToken" in out
        assert "Revenue" in out["formattedResponse"]
        assert "write_confirmed_by_user=true" in out["formattedResponse"]
        assert out["pendingCreate"]["domainId"] == 12


class TestTagCreateConfirmationPreview:
    def test_open_mode_no_parent_preview(self) -> None:
        out = governance_helpers._format_tag_create_confirmation_preview(
            tag_name="Logistics",
            description=None,
            secure_mode=False,
            master_tag_id=None,
            master_tag_name=None,
            parent_tag_id=None,
            parent_tag_name=None,
            create_directly_under_master=True,
        )
        assert out["workflowPhase"] == "confirm_create"
        assert out["doNotCreateTag"] is True
        assert out["tagSecurityMode"] == "open"
        assert "Logistics" in out["formattedResponse"]

    def test_secure_mode_under_parent_preview(self) -> None:
        out = governance_helpers._format_tag_create_confirmation_preview(
            tag_name="Child",
            description="<p>x</p>",
            secure_mode=True,
            master_tag_id=10,
            master_tag_name="Finance",
            parent_tag_id=20,
            parent_tag_name="Cost Center",
            create_directly_under_master=False,
        )
        assert "SECURE" in out["formattedResponse"]
        assert "Cost Center" in out["formattedResponse"]
