"""
Machine-readable side-effect hints for MCP tool registrations.

MCP clients use these annotations to decide what a tool may do before it runs
(auto-approve reads, prompt on writes). They are advisory hints for the client —
authorization is always enforced server-side by OvalEdge RBAC/DAA. Keep them
truthful: an over-claimed `read_only` annotation lets a client skip a prompt on
a call that actually mutates governance metadata.

Python fields are MCP SDK v2 snake_case; the wire JSON still uses camelCase
aliases (``readOnlyHint``, ``destructiveHint``, …).
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

#: Read-only lookup against OvalEdge; never mutates catalog or governance state.
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)

#: Governed write that adds new governance objects (behind the confirm gate).
GOVERNED_CREATE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=True,
)

#: Governed write that overwrites existing values on an asset (confirm gate).
#: Destructive because the prior value is replaced, not appended to.
GOVERNED_UPDATE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)

#: Side-effecting but non-mutating: executes SQL on a source connection.
GOVERNED_EXECUTE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)

__all__ = [
    "GOVERNED_CREATE",
    "GOVERNED_EXECUTE",
    "GOVERNED_UPDATE",
    "READ_ONLY",
]
