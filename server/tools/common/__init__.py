"""Shared primitives for MCP tool modules."""

from server.tools.common.errors import error_payload, map_ovaledge_error
from server.tools.common.params import drop_none
from server.tools.common.runtime import (
    get_ovaledge_client,
    ovaledge_client,
    ovaledge_tool,
    set_ovaledge_client_factory,
)
from server.tools.common.validators import (
    as_dict,
    blank,
    mutual_exclusion,
    require_exactly_one_of,
    require_one_of,
    strip_or_none,
)

__all__ = [
    "as_dict",
    "blank",
    "drop_none",
    "error_payload",
    "get_ovaledge_client",
    "map_ovaledge_error",
    "mutual_exclusion",
    "ovaledge_client",
    "ovaledge_tool",
    "require_exactly_one_of",
    "require_one_of",
    "set_ovaledge_client_factory",
    "strip_or_none",
]
