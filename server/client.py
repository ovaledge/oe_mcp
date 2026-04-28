import json
import logging
from collections.abc import Callable
from typing import Any, cast

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from server.config import settings

logger = logging.getLogger(__name__)


def _log_outbound_request(request: httpx.Request) -> None:
    if not settings.ovaledge_log_http_requests:
        return
    logger.info("OvalEdge outbound %s %s", request.method, request.url)


def _ovaledge_authorization(token: str) -> str:
    return f"{settings.ovaledge_http_auth_scheme} {token}"


def _log_inbound_response(response: httpx.Response) -> None:
    if not settings.ovaledge_log_http_requests:
        return
    for hop in response.history:
        loc = hop.headers.get("location", "")
        logger.info("OvalEdge redirect hop %s Location=%s", hop.status_code, loc)
    logger.info("OvalEdge response %s %s", response.status_code, response.url)


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


def _success_response_as_dict(response: httpx.Response) -> dict[str, Any]:
    """
    Parse a successful (2xx) HTTP response body as JSON for tool payloads.

    OvalEdge sometimes returns empty bodies or HTML (e.g. misconfigured base URL,
    session/login pages). Avoid bare JSONDecodeError bubbling to MCP clients.
    """
    if not response.content:
        return {}
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        snippet = (response.text or "")[:400].replace("\n", " ")
        raise OvalEdgeError(
            502,
            f"HTTP {response.status_code} body is not JSON ({exc!s}). "
            f"Body starts with: {snippet!r}",
        ) from exc
    if isinstance(data, dict):
        return cast(dict[str, Any], data)
    return {"_json": data}


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
            "Authorization": _ovaledge_authorization(jwt) if jwt else "",
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
        auth = _ovaledge_authorization(token)
        self._headers["Authorization"] = auth
        if self._client is not None:
            self._client.headers["Authorization"] = auth

    async def _send_with_local_401_retry(
        self, build_request: Callable[[], httpx.Request]
    ) -> httpx.Response:
        assert self._client is not None, "Use OvalEdgeClient as async context manager"
        retried_401 = False
        while True:
            await self._ensure_local_token()
            req = build_request()
            _log_outbound_request(req)
            response = await self._client.send(req)
            _log_inbound_response(response)
            if (
                not retried_401
                and settings.auth_mode == "local"
                and response.status_code == 401
            ):
                from server.auth.token_exchange import invalidate_local_jwt_cache

                invalidate_local_jwt_cache()
                retried_401 = True
                continue
            return response

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

        def build_request() -> httpx.Request:
            assert self._client is not None
            return self._client.build_request("GET", path, params=params)

        response = await self._send_with_local_401_retry(build_request)
        self._raise_for_status(response)
        return _success_response_as_dict(response)

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

        def build_request() -> httpx.Request:
            assert self._client is not None
            return self._client.build_request("POST", path, json=body)

        response = await self._send_with_local_401_retry(build_request)
        self._raise_for_status(response)
        return _success_response_as_dict(response)

    def _raise_for_status(self, response: httpx.Response) -> None:
        if 300 <= response.status_code < 400:
            loc = response.headers.get("location", "")
            raise OvalEdgeError(
                response.status_code,
                f"HTTP redirect (Location={loc!r}). Spring may require session login "
                "for this path; ensure /api/v1/mcp/** accepts Authorization: "
                f"{settings.ovaledge_http_auth_scheme} <jwt> like token/generate.",
            )
        if response.status_code < 400:
            return
        if settings.ovaledge_log_http_requests:
            preview = (response.text or "").replace("\n", " ")[:800]
            logger.info(
                "OvalEdge HTTP %s error body (truncated): %s",
                response.status_code,
                preview,
            )
        try:
            detail = response.json().get("message", response.text)
        except Exception:
            detail = response.text

        if response.status_code in (429, 502, 503, 504):
            raise OvalEdgeTransientError(response.status_code, str(detail))
        raise OvalEdgeError(response.status_code, str(detail))
