"""Shared primitives for MCP tool modules."""

from server.tools.common.descriptions import classify_tool_desc
from server.tools.common.errors import error_payload, map_ovaledge_error
from server.tools.common.params import drop_none
from server.tools.common.runtime import (
    get_ovaledge_client,
    ovaledge_client,
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
    "classify_tool_desc",
    "drop_none",
    "error_payload",
    "get_ovaledge_client",
    "map_ovaledge_error",
    "mutual_exclusion",
    "ovaledge_client",
    "require_exactly_one_of",
    "require_one_of",
    "set_ovaledge_client_factory",
    "strip_or_none",
]
