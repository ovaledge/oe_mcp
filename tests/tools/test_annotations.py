"""Governed-write annotation profiles (MCP SDK v2 snake_case / camelCase wire)."""

from __future__ import annotations

from server.tools.common.annotations import (
    GOVERNED_CREATE,
    GOVERNED_EXECUTE,
    GOVERNED_UPDATE,
    READ_ONLY,
)


def test_annotation_profiles_serialize_camelcase_on_the_wire() -> None:
    """Clients still receive MCP JSON aliases; Python uses snake_case fields."""
    read_only = READ_ONLY.model_dump(by_alias=True)
    assert read_only["readOnlyHint"] is True
    assert read_only["destructiveHint"] is False

    create = GOVERNED_CREATE.model_dump(by_alias=True)
    assert create["readOnlyHint"] is False
    assert create["destructiveHint"] is False

    update = GOVERNED_UPDATE.model_dump(by_alias=True)
    assert update["readOnlyHint"] is False
    assert update["destructiveHint"] is True

    execute = GOVERNED_EXECUTE.model_dump(by_alias=True)
    assert execute["readOnlyHint"] is False
    assert execute["idempotentHint"] is True
