"""Governance role update helpers."""

from __future__ import annotations

from typing import Any

from server.constants import (
    MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC,
    MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES,
    MCP_PATH_UPDATE_GOVERNANCE_ROLES,
)
from server.tools.common.confirm_gate import attach_confirmation_token
from server.tools.common.descriptions import classify_tool_desc
from server.tools.governance._shared import (
    _CREATE_CONFIRM_AGENT_INSTRUCTION,
    _ROLE_KEYS_CANONICAL,
)

_DESC_UPDATE_GOVERNANCE_ROLES = classify_tool_desc(
    "Assign or update governance responsibilities (Owner, Steward, Custodian, "
    "Governance Role 4/5/6) on supported OvalEdge assets.\n\n"
    f"Backend: POST {MCP_PATH_UPDATE_GOVERNANCE_ROLES}\n\n"
    "**Human confirmation (same pattern as create_glossary_term / create_tag):** "
    "When ready to persist (and dry_run is not true), call without "
    "write_confirmed_by_user to receive a confirm_update preview (doNotUpdate=true). "
    "Show formattedResponse; wait for explicit user approval. Re-call with "
    "write_confirmed_by_user=true and the same object_id, object_type, role_updates, "
    "and clientContext — then POST. Never set write_confirmed_by_user until the user "
    "confirms.\n\n"
    "Workflow — resolve the target first:\n"
    "- Catalog assets (tables, columns, files, schemas, reports, APIs, queries, glossary, "
    "tags, stories): use asset_explorer, then pass items[].objectId and objectType.\n"
    "- Data Quality rules: use dq_rule_advisor (step=lookup) "
    "(asset_explorer does NOT index dqrule). "
    "Then update_governance_roles with object_type dqrule and role_updates.steward only.\n"
    "- Other non-catalog governance targets (if you already have ids): "
    f"object_type one of {MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC}.\n\n"
    "role_updates: each key is a role name; each value must be a non-empty user/team id. "
    "Roles cannot be cleared (null/empty/whitespace → HTTP 400).\n\n"
    "Role keys (case-insensitive): owner, steward, custodian, governance_role_4, "
    "governance_role_5, governance_role_6.\n\n"
    f"Steward-only object types: {', '.join(sorted(MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES))} "
    "(owner/custodian/gov 4–6 are rejected with HTTP 400).\n\n"
    "The server enforces RBAC and governance propagation rules. If a role is inherited from "
    "a glossary term via a 'Copy <Role> to Catalog' setting, that role update will be blocked "
    "and returned in blockedRoles with reasonCode=GLOSSARY_PROPAGATED_GOVERNANCE_ROLE. "
    "Multi-role requests may return partial_success.\n\n"
    "Responses include a redirectUrl to open the target object in OvalEdge."
)
def _normalize_role_updates(
    role_updates: dict[str, str | None] | None,
) -> tuple[dict[str, str] | None, str | None]:
    """
    Return (normalized_updates_or_none, error_or_none).

    The tool accepts a dict whose keys are role names; we normalize keys to the canonical set.
    A governance role must always be assigned to a valid user or team — empty/none/null
    values are rejected so a role can never be cleared or left without an assignee.
    """
    if role_updates is None:
        return None, "Provide role_updates with at least one role."
    if not isinstance(role_updates, dict) or not role_updates:
        return None, "Provide role_updates with at least one role."
    normalized: dict[str, str] = {}
    invalid: list[str] = []
    empty_value_roles: list[str] = []
    for k, v in role_updates.items():
        key = str(k or "").strip().lower()
        canon = _ROLE_KEYS_CANONICAL.get(key)
        if not canon:
            invalid.append(str(k))
            continue
        user = "" if v is None else str(v).strip()
        if user == "":
            empty_value_roles.append(canon)
            continue
        normalized[canon] = user
    if invalid:
        return (
            None,
            "Invalid governance role type(s): "
            + ", ".join(sorted({s for s in invalid if str(s).strip()})),
        )
    if empty_value_roles:
        return (
            None,
            "Governance roles cannot be empty/none. Provide a valid user or team id for: "
            + ", ".join(sorted(set(empty_value_roles)))
            + ". A governance role cannot be cleared or unset.",
        )
    if not normalized:
        return None, "Provide role_updates with at least one valid role."
    return normalized, None


def _format_update_governance_roles_response(body: dict[str, Any]) -> str:
    status = str(body.get("status") or "").strip()
    lines: list[str] = []
    if status:
        lines.append(f"**Status:** {status}")
    target = body.get("target")
    if isinstance(target, dict):
        oid = target.get("objectId")
        otype = target.get("objectType")
        if oid is not None and otype:
            lines.append(f"**Target:** {otype} (id {oid})")
        redirect = str(target.get("redirectUrl") or "").strip()
        if redirect:
            lines.append(f"**Open in OvalEdge:** {redirect}")

    reason_code = str(body.get("reasonCode") or "").strip()
    if reason_code:
        lines.append(f"**Reason code:** {reason_code}")

    updated = body.get("updatedRoles")
    if isinstance(updated, list) and updated:
        lines.append(f"**Updated roles:** {', '.join(str(r) for r in updated)}")
    blocked = body.get("blockedRoles")
    if isinstance(blocked, list) and blocked:
        lines.append(f"**Blocked roles:** {', '.join(str(r) for r in blocked)}")

    message = str(body.get("message") or "").strip()
    if message:
        lines.append(message)
    return "\n".join(lines).strip()


def _enrich_update_governance_roles_response(body: dict[str, Any]) -> dict[str, Any]:
    formatted = _format_update_governance_roles_response(body)
    if formatted:
        body["formattedResponse"] = formatted
    return body


def _format_update_governance_roles_confirmation_preview(
    body: dict[str, Any],
) -> dict[str, Any]:
    target = body.get("target")
    oid = otype = None
    if isinstance(target, dict):
        oid = target.get("objectId")
        otype = target.get("objectType")
    role_updates = body.get("roleUpdates")
    role_lines: list[str] = []
    if isinstance(role_updates, dict):
        for role, principal in sorted(role_updates.items()):
            role_lines.append(f"- **{role}:** {principal}")
    roles_block = "\n".join(role_lines) if role_lines else "- (no role_updates)"
    dry = body.get("options", {})
    dry_note = ""
    if isinstance(dry, dict) and dry.get("dryRun"):
        dry_note = "\n- **Note:** dry_run=true — validate only on confirm.\n"
    preview = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm governance role update**\n\n"
            f"- **Target:** {otype} (id {oid})\n"
            f"{roles_block}\n"
            f"{dry_note}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same object_id, object_type, role_updates, and clientContext."
        ),
        "agentInstruction": _CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingUpdate": {
            "target": target,
            "roleUpdates": role_updates,
        },
    }
    return attach_confirmation_token(preview, body)


