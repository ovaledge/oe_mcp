"""Input validation helpers shared across tool modules."""

from __future__ import annotations

from typing import Any

from server.tools.common.errors import error_payload


def as_dict(value: object) -> dict[str, Any]:
    """Narrow arbitrary JSON/object values to a dict for type checkers."""
    return value if isinstance(value, dict) else {}


def require_one_of(
    fields: dict[str, bool],
    *,
    message: str = "Provide one of the required identifiers.",
) -> dict[str, Any] | None:
    if any(fields.values()):
        return None
    return error_payload(message)


def require_exactly_one_of(
    fields: dict[str, bool],
    *,
    both_message: str,
    neither_message: str,
) -> dict[str, Any] | None:
    present = [name for name, ok in fields.items() if ok]
    if len(present) > 1:
        return error_payload(both_message)
    if not present:
        return error_payload(neither_message)
    return None


def blank(s: str | None) -> bool:
    return s is None or str(s).strip() == ""


def strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def mutual_exclusion(
    *pairs: tuple[bool, bool],
    message: str,
) -> dict[str, Any] | None:
    for a, b in pairs:
        if a and b:
            return error_payload(message)
    return None
