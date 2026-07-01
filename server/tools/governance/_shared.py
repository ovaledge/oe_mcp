"""Shared constants and utilities for governance tool helpers."""

from __future__ import annotations


def _cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


_CREATE_CONFIRM_AGENT_INSTRUCTION = (
    "Show formattedResponse and wait for explicit user approval. "
    "Do not set write_confirmed_by_user=true until the user confirms. "
    "Then re-call with write_confirmed_by_user=true, confirmation_token from the "
    "preview, and the same parameters."
)

_ROLE_KEYS_CANONICAL: dict[str, str] = {
    "owner": "owner",
    "steward": "steward",
    "custodian": "custodian",
    "governance_role_4": "governance_role_4",
    "governance_role_5": "governance_role_5",
    "governance_role_6": "governance_role_6",
    "governancerole4": "governance_role_4",
    "governancerole5": "governance_role_5",
    "governancerole6": "governance_role_6",
    "govrole4": "governance_role_4",
    "govrole5": "governance_role_5",
    "govrole6": "governance_role_6",
    "gov_role_4": "governance_role_4",
    "gov_role_5": "governance_role_5",
    "gov_role_6": "governance_role_6",
}
