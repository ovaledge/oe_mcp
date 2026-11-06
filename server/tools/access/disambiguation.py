"""Server-side who-has-access disambiguation gate for access MCP tools."""

from __future__ import annotations

import re
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


def _contains_signal(question: str, keyword: str) -> bool:
    """Match a signal keyword as a whole word/phrase (case-insensitive)."""
    pattern = r"\b" + re.escape(keyword).replace(r"\ ", r"\s+") + r"\b"
    return re.search(pattern, question, flags=re.IGNORECASE) is not None


def detect_access_intent_from_question(question: str) -> str | None:
    """
    Infer who-has-access intent from explicit signals in the user question.

    Returns ``native``, ``catalog_acl``, or ``None`` when disambiguation is required.
    Platform names (Snowflake/Redshift/Tableau) alone never return an intent.
    """
    q = (question or "").strip()
    if not q:
        return None
    for keyword in MCP_ACCESS_CATALOG_ACL_SIGNAL_KEYWORDS:
        if _contains_signal(q, keyword):
            return MCP_ACCESS_INTENT_CATALOG_ACL
    for keyword in MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS:
        if _contains_signal(q, keyword):
            return MCP_ACCESS_INTENT_NATIVE
    return None


def validate_access_intent_confirmed(
    access_intent_confirmed: str | None,
    *,
    query_direction: str,
    expected_intent: str,
) -> dict[str, Any] | None:
    """
    Block who-has-access tool calls until the user picks native (1) or catalog permissions (2).

    ``user_to_objects``, ``user_to_object``, and ``browse`` are not gated.
    """
    qd = (query_direction or "").strip().lower()
    if expected_intent == MCP_ACCESS_INTENT_NATIVE and qd not in _WHO_HAS_ACCESS_DIRECTIONS_SOURCE:
        return None
    if (
        expected_intent == MCP_ACCESS_INTENT_CATALOG_ACL
        and qd not in _WHO_HAS_ACCESS_DIRECTIONS_CATALOG
    ):
        return None

    confirmed = (access_intent_confirmed or "").strip().lower()
    if confirmed == expected_intent:
        return None

    return error_payload(
        "Who-has-access requires disambiguation before calling this tool.",
        error_code="ACCESS_INTENT_REQUIRED",
        advisoryMessage=MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
        formattedResponse=MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
        accessIntentRequired=expected_intent,
        queryDirection=qd,
    )
