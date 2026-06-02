"""Tool execution runtime: client factory and error-mapping decorator."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from server.client import OvalEdgeClient, OvalEdgeError
from server.tools.common.errors import map_ovaledge_error

P = ParamSpec("P")
R = TypeVar("R")

_client_factory: Callable[[], OvalEdgeClient] = OvalEdgeClient


def get_ovaledge_client() -> OvalEdgeClient:
    return _client_factory()


def set_ovaledge_client_factory(factory: Callable[[], OvalEdgeClient] | None) -> None:
    """Override client construction (tests). Pass None to reset to OvalEdgeClient."""
    global _client_factory
    _client_factory = factory or OvalEdgeClient


@asynccontextmanager
async def ovaledge_client() -> AsyncIterator[OvalEdgeClient]:
    """Async context manager for a single OvalEdge HTTP client (uses injectable factory)."""
    client = get_ovaledge_client()
    async with client:
        yield client


def ovaledge_tool[**P, R](
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R | dict[str, Any]]]:
    """Map OvalEdgeError to standard MCP error payload; leave other exceptions raised."""

    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | dict[str, Any]:
        try:
            return await fn(*args, **kwargs)
        except OvalEdgeError as exc:
            return map_ovaledge_error(exc)

    return wrapper
