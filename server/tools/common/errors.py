"""Consistent OvalEdge error payloads for MCP tool responses."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError


def error_payload(
    message: str,
    status_code: int = 400,
    *,
    error_code: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {"error": message, "status_code": status_code}
    if error_code is not None:
        out["error_code"] = error_code
    out.update(extra)
    return out


def map_ovaledge_error(exc: OvalEdgeError) -> dict[str, Any]:
    code: str | None = None
    if exc.body:
        raw_code = exc.body.get("code")
        if raw_code is not None and str(raw_code).strip():
            code = str(raw_code).strip()
    return error_payload(str(exc), status_code=exc.status_code, error_code=code)
