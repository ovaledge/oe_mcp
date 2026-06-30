"""Server-side who-has-access disambiguation gate for access MCP tools."""

from __future__ import annotations

from typing import Any

from server.constants import (
    MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
    MCP_ACCESS_INTENT_CATALOG_ACL,
    MCP_ACCESS_INTENT_NATIVE,
)
from server.tools.common.errors import error_payload

_WHO_HAS_ACCESS_DIRECTIONS_SOURCE = frozenset({"object_to_users"})
_WHO_HAS_ACCESS_DIRECTIONS_CATALOG = frozenset({"object_to_principals"})


def validate_access_intent_confirmed(
    access_intent_confirmed: str | None,
    *,
    query_direction: str,
    expected_intent: str,
) -> dict[str, Any] | None:
    """
  Block who-has-access tool calls until the user picks native (1) or catalog ACL (2).

  ``user_to_objects``, ``user_to_object``, and ``browse`` are not gated.
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

    return error_payload(
        "Who-has-access requires disambiguation before calling this tool.",
        error_code="ACCESS_INTENT_REQUIRED",
        advisoryMessage=MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
        formattedResponse=MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
        accessIntentRequired=expected_intent,
        queryDirection=qd,
    )
