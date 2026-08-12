"""
Machine-readable side-effect hints for MCP tool registrations.

MCP clients use these annotations to decide what a tool may do before it runs
(auto-approve reads, prompt on writes). They are advisory hints for the client —
authorization is always enforced server-side by OvalEdge RBAC/DAA. Keep them
truthful: an over-claimed `read_only` annotation lets a client skip a prompt on
a call that actually mutates governance metadata.
"""

from __future__ import annotations

from typing import Any

_ToolAnnotations = dict[str, Any]

#: Read-only lookup against OvalEdge; never mutates catalog or governance state.
READ_ONLY: _ToolAnnotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

#: Governed write that adds new governance objects (behind the confirm gate).
GOVERNED_CREATE: _ToolAnnotations = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}

#: Governed write that overwrites existing values on an asset (confirm gate).
#: Destructive because the prior value is replaced, not appended to.
GOVERNED_UPDATE: _ToolAnnotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}

#: Side-effecting but non-mutating: executes SQL on a source connection.
GOVERNED_EXECUTE: _ToolAnnotations = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

__all__ = [
    "GOVERNED_CREATE",
    "GOVERNED_EXECUTE",
    "GOVERNED_UPDATE",
    "READ_ONLY",
]
