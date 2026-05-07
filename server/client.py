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


def _response_body_text_for_auth_heuristic(response: httpx.Response) -> str:
    """Best-effort string for OvalEdge revoked-JWT detection; supports JSON or plain text."""
    if not response.content:
        return ""
    try:
        data = response.json()
    except json.JSONDecodeError:
        return response.text or ""
    if isinstance(data, dict):
        parts: list[str] = []
        for k in ("message", "error", "error_description", "detail"):
            v = data.get(k)
            if v is not None and str(v).strip():
                parts.append(str(v))
        return " ".join(parts) if parts else (response.text or "")
    return str(data)


def _suggests_revoked_oval_edge_session_jwt(body_text: str) -> bool:
    """
    OvalEdge may return HTTP 400 (not only 401) when the JWT was superseded elsewhere
    (single active token per user token+secret). Match common API copy without being too broad.
    """
    t = body_text.lower()
    return "invalid token" in t or "please generate a new token" in t


def _oval_edge_revoked_session_jwt_response(response: httpx.Response) -> bool:
    if response.status_code not in (400, 401):
        return False
    return _suggests_revoked_oval_edge_session_jwt(_response_body_text_for_auth_heuristic(response))


async def _evict_remote_credentials_jwt_cache() -> None:
    from server.auth.context import current_oe_credential_cache_key
    from server.auth.credentials_cache import get_default_credentials_cache

    cache_key = current_oe_credential_cache_key.get()
    if cache_key:
        await get_default_credentials_cache().delete_entry(cache_key)


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

    async def _try_refresh_remote_oe_jwt(self) -> bool:
        """
        After cache eviction, call token/generate again and update client headers.

        Requires ``current_oe_user_token`` / ``current_oe_user_secret`` set by remote auth middleware.
        """
        from server.auth.context import current_oe_jwt, current_oe_user_secret, current_oe_user_token
        from server.auth.token_exchange import TokenExchangeError, get_or_refresh_user_token

        ut = current_oe_user_token.get()
        us = current_oe_user_secret.get()
        if not ut or not us:
            logger.warning(
                "Cannot refresh OvalEdge JWT: missing credential context "
                "(current_oe_user_token / current_oe_user_secret)"
            )
            return False
        try:
            new_jwt = await get_or_refresh_user_token(ut, us)
        except TokenExchangeError as e:
            logger.warning("OvalEdge JWT refresh after revoked session failed: %s", e)
            return False
        except Exception as e:
            logger.warning("OvalEdge JWT refresh after revoked session unexpected error: %s", e)
            return False
        current_oe_jwt.set(new_jwt)
        auth = _ovaledge_authorization(new_jwt)
        self._headers["Authorization"] = auth
        if self._client is not None:
            self._client.headers["Authorization"] = auth
        return True

    async def _send_with_401_handling(
        self, build_request: Callable[[], httpx.Request]
    ) -> httpx.Response:
        assert self._client is not None, "Use OvalEdgeClient as async context manager"
        retried_401_local = False
        retried_remote_revoked_jwt = False
        while True:
            await self._ensure_local_token()
            req = build_request()
            _log_outbound_request(req)
            response = await self._client.send(req)
            _log_inbound_response(response)
            if (
                not retried_401_local
                and settings.auth_mode == "local"
                and response.status_code == 401
            ):
                from server.auth.token_exchange import invalidate_local_jwt_cache

                invalidate_local_jwt_cache()
                retried_401_local = True
                continue

            if settings.auth_mode == "remote_credentials":
                invalidated_elsewhere = _oval_edge_revoked_session_jwt_response(response)
                if response.status_code == 401 or invalidated_elsewhere:
                    await _evict_remote_credentials_jwt_cache()
                if (
                    invalidated_elsewhere
                    and not retried_remote_revoked_jwt
                    and await self._try_refresh_remote_oe_jwt()
                ):
                    retried_remote_revoked_jwt = True
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

        response = await self._send_with_401_handling(build_request)
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

        response = await self._send_with_401_handling(build_request)
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
