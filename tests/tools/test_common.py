"""Unit tests for server.tools.common."""

from server.client import OvalEdgeError
from server.tools.common import (
    blank,
    drop_none,
    error_payload,
    map_ovaledge_error,
    require_exactly_one_of,
    strip_or_none,
)
from server.tools.common.runtime import ovaledge_client, set_ovaledge_client_factory


class TestDropNone:
    def test_omits_none(self) -> None:
        assert drop_none(a=1, b=None, c="x") == {"a": 1, "c": "x"}


class TestValidators:
    def test_require_exactly_one_both(self) -> None:
        err = require_exactly_one_of(
            {"id": True, "name": True},
            both_message="both",
            neither_message="neither",
        )
        assert err is not None
        assert err["status_code"] == 400

    def test_blank(self) -> None:
        assert blank("") is True
        assert blank("  ") is True
        assert blank("x") is False


class TestErrors:
    def test_map_ovaledge_error(self) -> None:
        exc = OvalEdgeError(404, "not found")
        assert map_ovaledge_error(exc) == error_payload(
            str(exc), status_code=404
        )


class TestStripOrNone:
    def test_strip_or_none(self) -> None:
        assert strip_or_none("  x  ") == "x"
        assert strip_or_none("   ") is None
        assert strip_or_none(None) is None


class TestOvaledgeClientSession:
    async def test_ovaledge_client_uses_factory(self) -> None:
        from unittest.mock import AsyncMock

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        set_ovaledge_client_factory(lambda: mock_client)
        try:
            async with ovaledge_client() as client:
                assert client is mock_client
        finally:
            set_ovaledge_client_factory(None)
