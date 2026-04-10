from typing import Any, cast

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from server.config import settings


class OvalEdgeError(Exception):
    """Raised for non-retryable OvalEdge API errors (4xx except 429)."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"OvalEdge API error {status_code}: {message}")


class OvalEdgeTransientError(OvalEdgeError):
    """Raised for retryable errors: 429, 502, 503, 504."""

    pass


def _is_transient(exc: BaseException) -> bool:
    return isinstance(exc, OvalEdgeTransientError)


class OvalEdgeClient:
    """
    Stateless async HTTP client for OvalEdge REST APIs.
    Use as async context manager — one instance per tool call.

    Usage:
        async with OvalEdgeClient() as client:
            result = await client.get("/api/some/path")

    JWT is sourced from current_oe_jwt ContextVar,
    set by auth middleware before tool invocation.
    """

    def __init__(self) -> None:
        from server.auth.context import current_oe_jwt

        jwt = current_oe_jwt.get()
        # In local mode, token can be lazily refreshed in _ensure_local_token().
        if not jwt and settings.auth_mode != "local":
            raise RuntimeError(
                "No OvalEdge JWT in context. "
                "Auth middleware must set current_oe_jwt before tool calls."
            )
        self._base_url = settings.ovaledge_base_url
        self._headers = {
            "Authorization": f"Bearer {jwt}" if jwt else "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._timeout = settings.ovaledge_timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OvalEdgeClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _ensure_local_token(self) -> None:
        """
        Keep local-mode JWT valid by refreshing if expired/expiring.
        Remote mode always receives per-request token via middleware.
        """
        if settings.auth_mode != "local":
            return
        from server.auth.token_exchange import get_or_refresh_local_token

        token = await get_or_refresh_local_token()
        self._headers["Authorization"] = f"Bearer {token}"
        if self._client is not None:
            self._client.headers["Authorization"] = f"Bearer {token}"

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(settings.ovaledge_max_retries),
        wait=wait_exponential(
            multiplier=settings.ovaledge_retry_backoff_seconds,
            min=0.5,
            max=10,
        ),
        reraise=True,
    )
    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self._client is not None, "Use OvalEdgeClient as async context manager"
        await self._ensure_local_token()
        response = await self._client.get(path, params=params)
        self._raise_for_status(response)
        return cast(dict[str, Any], response.json())

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(settings.ovaledge_max_retries),
        wait=wait_exponential(
            multiplier=settings.ovaledge_retry_backoff_seconds,
            min=0.5,
            max=10,
        ),
        reraise=True,
    )
    async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        assert self._client is not None, "Use OvalEdgeClient as async context manager"
        await self._ensure_local_token()
        response = await self._client.post(path, json=body)
        self._raise_for_status(response)
        return cast(dict[str, Any], response.json())

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        try:
            detail = response.json().get("message", response.text)
        except Exception:
            detail = response.text

        if response.status_code in (429, 502, 503, 504):
            raise OvalEdgeTransientError(response.status_code, str(detail))
        raise OvalEdgeError(response.status_code, str(detail))
