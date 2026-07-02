"""Helpers for governed-write tests that require confirmation tokens."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from server.tools.common.confirm_gate import compute_confirmation_token


def confirmation_token_for_payload(payload: dict[str, Any]) -> str:
    return compute_confirmation_token(payload)


def write_confirm_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "write_confirmed_by_user": True,
        "confirmation_token": compute_confirmation_token(payload),
    }


async def invoke_write_confirmed(
    fn: Callable[..., Awaitable[dict[str, Any]]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Preview then POST with matching confirmation_token (governed-write tests)."""
    clean = {
        k: v
        for k, v in kwargs.items()
        if k not in ("write_confirmed_by_user", "confirmation_token")
    }
    preview = await fn(**clean)
    return await fn(
        **clean,
        write_confirmed_by_user=True,
        confirmation_token=preview["confirmationToken"],
    )
