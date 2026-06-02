"""Unit tests for data story section parsing in governance tools."""

from server.tools.governance import helpers as governance_helpers


class TestParseStorySections:
    def test_html_headings(self) -> None:
        html = (
            "<h3>Scope</h3><p>Applies to critical PII.</p>"
            "<h3>Cadence</h3><p>Quarterly review.</p>"
        )
        sections = governance_helpers._parse_story_sections(html)
        assert sections == [
            ("Scope", "Applies to critical PII."),
            ("Cadence", "Quarterly review."),
        ]

    def test_plain_text_fallback(self) -> None:
        sections = governance_helpers._parse_story_sections("Single paragraph body.")
        assert sections == [("", "Single paragraph body.")]
