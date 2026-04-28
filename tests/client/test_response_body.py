"""Tests for OvalEdge HTTP response parsing (empty / non-JSON success bodies)."""

import httpx
import pytest

from server.client import OvalEdgeError, _success_response_as_dict


def test_empty_body_returns_empty_dict() -> None:
    r = httpx.Response(200, content=b"")
    assert _success_response_as_dict(r) == {}


def test_valid_object_passthrough() -> None:
    r = httpx.Response(200, json={"a": 1})
    assert _success_response_as_dict(r) == {"a": 1}


def test_valid_array_wrapped() -> None:
    r = httpx.Response(200, json=[1, 2])
    assert _success_response_as_dict(r) == {"_json": [1, 2]}


def test_non_json_raises_ovaledge_error() -> None:
    r = httpx.Response(200, content=b"<html>login</html>")
    with pytest.raises(OvalEdgeError) as ei:
        _success_response_as_dict(r)
    assert ei.value.status_code == 502
    assert "not json" in str(ei.value).lower()
