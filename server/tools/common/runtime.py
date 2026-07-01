"""Tool execution runtime: injectable OvalEdge client factory."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from server.client import OvalEdgeClient

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
