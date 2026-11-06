"""Shared constants and utilities for governance tool helpers."""

from __future__ import annotations

from server.tools.common.confirm_gate import CREATE_CONFIRM_AGENT_INSTRUCTION
from server.tools.common.formatting import cell


def _cell(value: object) -> str:
    return cell(value)


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


_CREATE_CONFIRM_AGENT_INSTRUCTION = CREATE_CONFIRM_AGENT_INSTRUCTION


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
