"""Unit tests for payload-bound write confirmation tokens."""

from __future__ import annotations

from server.tools.common.confirm_gate import (
    attach_confirmation_token,
    compute_confirmation_token,
    verify_write_confirmation,
)


def test_compute_confirmation_token_is_stable_for_key_order() -> None:
    a = {"target": {"objectId": 1, "objectType": "oetable"}, "descriptions": {"x": 1}}
    b = {"descriptions": {"x": 1}, "target": {"objectType": "oetable", "objectId": 1}}
    assert compute_confirmation_token(a) == compute_confirmation_token(b)


def test_attach_confirmation_token_adds_digest() -> None:
    payload = {"termName": "Revenue", "domainId": 12}
    preview = attach_confirmation_token({"ok": True, "workflowPhase": "confirm_create"}, payload)
    assert preview["confirmationToken"] == compute_confirmation_token(payload)


def test_verify_write_confirmation_requires_token_when_confirmed() -> None:
    payload = {"roleUpdates": {"steward": "alice"}}
    err = verify_write_confirmation(
        payload,
        write_confirmed_by_user=True,
        confirmation_token=None,
    )
    assert err is not None
    assert err.get("error_code") == "confirmation_token_mismatch"
    assert err.get("expectedConfirmationToken") == compute_confirmation_token(payload)


def test_verify_write_confirmation_rejects_stale_token() -> None:
    err = verify_write_confirmation(
        {"termName": "Revenue", "domainId": 99},
        write_confirmed_by_user=True,
        confirmation_token=compute_confirmation_token({"termName": "Revenue", "domainId": 12}),
    )
    assert err is not None
    assert err["error_code"] == "confirmation_token_mismatch"


def test_verify_write_confirmation_passes_matching_token() -> None:
    payload = {"targets": [{"objectId": 9, "objectType": "oetable"}]}
    token = compute_confirmation_token(payload)
    assert (
        verify_write_confirmation(
            payload,
            write_confirmed_by_user=True,
            confirmation_token=token,
        )
        is None
    )


def test_verify_write_confirmation_skipped_when_not_confirmed() -> None:
    assert (
        verify_write_confirmation(
            {"x": 1},
            write_confirmed_by_user=False,
            confirmation_token=None,
        )
        is None
    )
