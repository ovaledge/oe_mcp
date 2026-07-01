"""Server-side who-has-access disambiguation gate for access MCP tools."""

from __future__ import annotations

from typing import Any

from server.constants import (
    MCP_ACCESS_CATALOG_ACL_SIGNAL_KEYWORDS,
    MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
    MCP_ACCESS_INTENT_CATALOG_ACL,
    MCP_ACCESS_INTENT_NATIVE,
    MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS,
)
from server.tools.common.errors import error_payload

_WHO_HAS_ACCESS_DIRECTIONS_SOURCE = frozenset({"object_to_users"})
_WHO_HAS_ACCESS_DIRECTIONS_CATALOG = frozenset({"object_to_principals"})


def question_has_native_access_signals(question: str | None) -> bool:
    """True when the question text includes native/DAM routing signals."""
    return _question_has_signal(question, MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS)


def question_has_catalog_acl_access_signals(question: str | None) -> bool:
    """True when the question text includes OvalEdge catalog ACL routing signals."""
    return _question_has_signal(question, MCP_ACCESS_CATALOG_ACL_SIGNAL_KEYWORDS)


def infer_access_intent_from_question(question: str | None) -> str | None:
    """
    Infer who-has-access intent from question text.

    Returns None when ambiguous (no signals, or both native and catalog ACL signals).
    """
    has_native = question_has_native_access_signals(question)
    has_catalog_acl = question_has_catalog_acl_access_signals(question)
    if has_native and not has_catalog_acl:
        return MCP_ACCESS_INTENT_NATIVE
    if has_catalog_acl and not has_native:
        return MCP_ACCESS_INTENT_CATALOG_ACL
    return None


def _question_has_signal(question: str | None, keywords: tuple[str, ...]) -> bool:
    if not question or not str(question).strip():
        return False
    normalized = str(question).casefold()
    return any(keyword in normalized for keyword in keywords)


def validate_access_intent_confirmed(
    access_intent_confirmed: str | None,
    *,
    query_direction: str,
    expected_intent: str,
    user_question: str | None = None,
) -> dict[str, Any] | None:
    """
    Block who-has-access tool calls until the user picks native (1) or catalog ACL (2).

    ``user_to_objects``, ``user_to_object``, and ``browse`` are not gated.
    When ``access_intent_confirmed`` is omitted, matching signals in ``user_question``
    satisfy the gate for the expected intent.
    """
    qd = (query_direction or "").strip().lower()
    if expected_intent == MCP_ACCESS_INTENT_NATIVE:
        if qd not in _WHO_HAS_ACCESS_DIRECTIONS_SOURCE:
            return None
    elif expected_intent == MCP_ACCESS_INTENT_CATALOG_ACL:
        if qd not in _WHO_HAS_ACCESS_DIRECTIONS_CATALOG:
            return None
    else:
        return error_payload(
            f"Invalid access_intent_confirmed expectation: {expected_intent}",
            error_code="ACCESS_INTENT_INVALID",
        )

    confirmed = (access_intent_confirmed or "").strip().lower()
    if confirmed == expected_intent:
        return None

    inferred = infer_access_intent_from_question(user_question)
    if inferred == expected_intent:
        return None

    return error_payload(
        "Who-has-access requires disambiguation before calling this tool.",
        error_code="ACCESS_INTENT_REQUIRED",
        advisoryMessage=MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
        formattedResponse=MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
        accessIntentRequired=expected_intent,
        queryDirection=qd,
    )
