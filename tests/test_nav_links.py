"""Unit tests for server.nav_links."""

from server.nav_links import (
    build_absolute_nav_url,
    extract_hash_nav_link,
    normalize_nav_link,
)


class TestExtractHashNavLink:
    def test_hash_only(self) -> None:
        assert extract_hash_nav_link("#nav/story?id=1028") == "#nav/story?id=1028"

    def test_strips_absolute_prefix(self) -> None:
        assert (
            extract_hash_nav_link(
                "http://localhost:8080/ovaledge/#nav/story?id=1028"
            )
            == "#nav/story?id=1028"
        )

    def test_strips_duplicated_base(self) -> None:
        assert (
            extract_hash_nav_link(
                "http://localhost:8080/ovaledge/"
                "http://localhost:8080/ovaledge/#nav/story?id=1028"
            )
            == "#nav/story?id=1028"
        )

    def test_empty(self) -> None:
        assert extract_hash_nav_link("") == ""
        assert extract_hash_nav_link(None) == ""


class TestBuildAbsoluteNavUrl:
    def test_from_hash(self) -> None:
        assert (
            build_absolute_nav_url("#nav/story?id=1028")
            == "https://mock.ovaledge.com/#nav/story?id=1028"
        )

    def test_from_malformed_absolute(self) -> None:
        assert (
            build_absolute_nav_url(
                "http://localhost:8080/ovaledge/"
                "http://localhost:8080/ovaledge/#nav/story?id=1028"
            )
            == "https://mock.ovaledge.com/#nav/story?id=1028"
        )


class TestNormalizeNavLink:
    def test_rebuilds_absolute(self) -> None:
        rel, abs_url = normalize_nav_link(
            "http://localhost:8080/ovaledge/http://localhost:8080/ovaledge/#nav/story?id=1"
        )
        assert rel == "#nav/story?id=1"
        assert abs_url == "https://mock.ovaledge.com/#nav/story?id=1"
