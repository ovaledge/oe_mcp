"""Shared human-confirmation gate helpers for governed write tools."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from server.tools.common.errors import error_payload

CONFIRMATION_TOKEN_PARAM_DESCRIPTION = (
    "confirmationToken from the confirm_create/confirm_update preview; "
    "required with write_confirmed_by_user=true on the POST call."
)

CREATE_CONFIRM_AGENT_INSTRUCTION = (
    "Show formattedResponse and wait for explicit user approval. "
    "Do not set write_confirmed_by_user=true until the user confirms. "
    "Then re-call with write_confirmed_by_user=true, confirmation_token from the "
    "preview, and the same parameters."
)

_CONFIRMATION_TOKEN_MISMATCH = (
    "confirmation_token does not match the pending write payload. "
    "Re-run without write_confirmed_by_user for a fresh preview, then confirm "
    "with the same parameters and the returned confirmation_token."
)


def canonical_confirmation_payload(payload: dict[str, Any]) -> str:
    """Stable JSON for hashing write bodies (preview → confirmed POST binding)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_confirmation_token(payload: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical write payload."""
    digest = hashlib.sha256(canonical_confirmation_payload(payload).encode("utf-8")).hexdigest()
    return digest


def attach_confirmation_token(preview: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Add confirmationToken to a confirm_create / confirm_update preview response."""
    preview["confirmationToken"] = compute_confirmation_token(payload)
    return preview


def verify_write_confirmation(
    payload: dict[str, Any],
    *,
    write_confirmed_by_user: bool,
    confirmation_token: str | None,
) -> dict[str, Any] | None:
    """
    When write_confirmed_by_user is true, require confirmation_token to match payload.

    Returns an error dict on mismatch; None when verification passes or is not required.
    """
    if not write_confirmed_by_user:
        return None
    expected = compute_confirmation_token(payload)
    provided = (confirmation_token or "").strip()
    if not provided or provided != expected:
        return error_payload(
            _CONFIRMATION_TOKEN_MISMATCH,
            status_code=400,
            error_code="confirmation_token_mismatch",
            expectedConfirmationToken=expected,
        )
    return None
