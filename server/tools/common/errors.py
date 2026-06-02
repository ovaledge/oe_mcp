"""Consistent OvalEdge error payloads for MCP tool responses."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError


def error_payload(message: str, status_code: int = 400, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"error": message, "status_code": status_code}
    out.update(extra)
    return out


def map_ovaledge_error(exc: OvalEdgeError) -> dict[str, Any]:
    return error_payload(str(exc), status_code=exc.status_code)
