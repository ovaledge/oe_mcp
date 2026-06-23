"""Helpers for update_cde_associations MCP tool."""

from __future__ import annotations

from typing import Any

from server.constants import (
    MCP_CDE_ACTIONS,
    MCP_PATH_UPDATE_CDE_ASSOCIATIONS,
    MCP_UPDATE_CDE_OBJECT_TYPES,
)
from server.tools.common.descriptions import classify_tool_desc

_CDE_TYPE_ALIASES = {
    "apiobject": "oeapi",
    "apicolumn": "oeapicolumn",
    "filecolumn": "oefilecolumn",
    "code": "oequery",
}

_DESC_UPDATE_CDE = classify_tool_desc(
    "Update Critical Data Element (CDE) status on one or more catalog assets.\n\n"
    f"Backend: POST {MCP_PATH_UPDATE_CDE_ASSOCIATIONS}\n\n"
    "Use search_catalog_assets or catalog_asset_details first to resolve object_id "
    "and object_type when the user names an asset ambiguously.\n\n"
    "action must be Yes (mark as CDE), No (explicitly not critical), or None "
    "(remove CDE designation). Optional cde_category and cde_justification apply when "
    "marking or setting No; they are cleared when action is None.\n\n"
    "**Human confirmation:** Unless dry_run=true, the first call without "
    "create_confirmed_by_user returns a confirm_update preview (doNotUpdate=true). "
    "Re-call with create_confirmed_by_user=true after the user approves."
)

_UPDATE_CDE_CONFIRM_INSTRUCTION = (
    "Show formattedResponse and wait for explicit user approval. "
    "Do not set create_confirmed_by_user=true until the user confirms. "
    "Then re-call with create_confirmed_by_user=true and the same parameters."
)


def normalize_cde_object_type(object_type: str) -> str | None:
    key = object_type.strip().lower()
    canonical = _CDE_TYPE_ALIASES.get(key, key)
    return canonical if canonical in MCP_UPDATE_CDE_OBJECT_TYPES else None


def validate_cde_inputs(
    targets: list[dict[str, Any]] | None,
    action: str | None,
) -> dict[str, Any] | None:
    if not targets:
        return {
            "error": "targets must include at least one {object_id, object_type}.",
            "status_code": 400,
        }
    if not action or action.strip() not in MCP_CDE_ACTIONS:
        return {
            "error": f"action must be one of {sorted(MCP_CDE_ACTIONS)}, got {action!r}",
            "status_code": 400,
        }
    normalized_targets: list[dict[str, Any]] = []
    for item in targets:
        if not isinstance(item, dict):
            return {
                "error": "Each target must be an object with object_id and object_type.",
                "status_code": 400,
            }
        raw_type = item.get("object_type") or item.get("objectType")
        raw_id = item.get("object_id") if "object_id" in item else item.get("objectId")
        if raw_type is None or raw_id is None:
            return {
                "error": "Each target requires object_id and object_type.",
                "status_code": 400,
            }
        canonical = normalize_cde_object_type(str(raw_type))
        if canonical is None:
            return {
                "error": (
                    f"object_type must be one of {sorted(MCP_UPDATE_CDE_OBJECT_TYPES)}, "
                    f"got {raw_type!r}"
                ),
                "status_code": 400,
            }
        try:
            object_id = int(raw_id)
        except (TypeError, ValueError):
            return {"error": f"object_id must be an integer, got {raw_id!r}", "status_code": 400}
        if object_id <= 0:
            return {"error": "object_id must be a positive integer.", "status_code": 400}
        normalized_targets.append({"objectId": object_id, "objectType": canonical})
    return None


def build_update_cde_body(
    targets: list[dict[str, Any]],
    action: str,
    *,
    cde_category: str | None = None,
    cde_justification: str | None = None,
    dry_run: bool | None = None,
    idempotency_key: str | None = None,
    prompt: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    api_targets: list[dict[str, Any]] = []
    for item in targets:
        raw_type = item.get("object_type") or item.get("objectType")
        raw_id = item.get("object_id") if "object_id" in item else item.get("objectId")
        if raw_id is None or raw_type is None:
            raise ValueError("Each target requires object_id and object_type.")
        if isinstance(raw_id, bool) or not isinstance(raw_id, (int, str)):
            raise ValueError(f"object_id must be an integer, got {raw_id!r}")
        canonical = normalize_cde_object_type(str(raw_type))
        if canonical is None:
            raise ValueError(f"Unsupported object_type {raw_type!r}")
        api_targets.append({"objectId": int(raw_id), "objectType": canonical})
    body: dict[str, Any] = {
        "targets": api_targets,
        "action": action.strip(),
    }
    if cde_category is not None:
        body["cdeCategory"] = cde_category
    if cde_justification is not None:
        body["cdeJustification"] = cde_justification
    options: dict[str, Any] = {}
    if dry_run is not None:
        options["dryRun"] = dry_run
    if idempotency_key is not None and str(idempotency_key).strip():
        options["idempotencyKey"] = idempotency_key.strip()
    if options:
        body["options"] = options
    client_context: dict[str, str] = {}
    if prompt is not None and str(prompt).strip():
        client_context["prompt"] = str(prompt).strip()
    if reason is not None and str(reason).strip():
        client_context["reason"] = str(reason).strip()
    if client_context:
        body["clientContext"] = client_context
    return body


def format_update_cde_response(data: dict[str, Any]) -> str:
    lines: list[str] = []
    status = str(data.get("status") or "").strip()
    if status:
        lines.append(f"**Status:** {status}")
    summary = data.get("governanceSummary")
    if isinstance(summary, dict):
        lines.append(
            "**Summary:** "
            f"requested={summary.get('requested', 0)}, "
            f"updated={summary.get('updated', 0)}, "
            f"blocked={summary.get('blocked', 0)}, "
            f"noChange={summary.get('noChange', 0)}"
        )
    results = data.get("results")
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            otype = item.get("objectType")
            oid = item.get("objectId")
            updated = item.get("updatedCde") or item.get("previousCde")
            redirect = str(item.get("redirectUrl") or "").strip()
            blocked = item.get("blocked")
            no_change = item.get("noChange")
            prefix = f"- **{otype}** (id {oid})"
            if blocked:
                prefix += " [BLOCKED]"
            elif no_change:
                prefix += " [NO CHANGE]"
            lines.append(f"{prefix}: CDE={updated}")
            if redirect:
                lines.append(f"  - Open: {redirect}")
            message = str(item.get("message") or "").strip()
            if message:
                lines.append(f"  - {message}")
    audit = data.get("audit")
    if isinstance(audit, dict):
        source = audit.get("source")
        refs = audit.get("auditReferenceIds")
        if source:
            lines.append(f"**Audit source:** {source}")
        if isinstance(refs, list) and refs:
            lines.append(f"**Audit reference IDs:** {', '.join(str(r) for r in refs)}")
    return "\n".join(lines).strip()


def enrich_update_cde_response(data: dict[str, Any]) -> dict[str, Any]:
    formatted = format_update_cde_response(data)
    if formatted:
        data["formattedResponse"] = formatted
    return data


def format_update_cde_confirmation_preview(body: dict[str, Any]) -> dict[str, Any]:
    targets = body.get("targets") or []
    action = body.get("action")
    target_lines: list[str] = []
    if isinstance(targets, list):
        for t in targets:
            if isinstance(t, dict):
                target_lines.append(
                    f"- **{t.get('objectType')}** (id {t.get('objectId')}): action={action}"
                )
    dry_note = ""
    options = body.get("options")
    if isinstance(options, dict) and options.get("dryRun"):
        dry_note = "\n- **Note:** dry_run=true — preview only; no persist on confirm.\n"
    category = body.get("cdeCategory")
    justification = body.get("cdeJustification")
    meta_lines: list[str] = []
    if category is not None and str(category).strip():
        meta_lines.append(f"- **cdeCategory:** {category}")
    if justification is not None and str(justification).strip():
        preview = str(justification).strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."
        meta_lines.append(f"- **cdeJustification:** {preview}")
    meta_block = "\n".join(meta_lines) if meta_lines else ""
    return {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "createConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm CDE update**\n\n"
            + "\n".join(target_lines)
            + (f"\n{meta_block}" if meta_block else "")
            + f"{dry_note}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`create_confirmed_by_user=true` and the same targets, action, and optional fields."
        ),
        "agentInstruction": _UPDATE_CDE_CONFIRM_INSTRUCTION,
        "pendingUpdate": body,
    }
