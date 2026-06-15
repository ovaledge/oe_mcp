import os
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Cursor / IDE MCP subprocesses often start with cwd ≠ project root; a relative
# ".env" would then be missed and OVALEDGE_BASE_URL falls back to the mock default.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.is_file() else (),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── OvalEdge connection ──────────────────────────────────────
    # Default supports local tooling/CI; always set OVALEDGE_BASE_URL in real deployments.
    ovaledge_base_url: str = "https://mock.ovaledge.com"
    # Optional override for user-facing nav links (pod/custom hostname); falls back to base URL.
    ovaledge_link_base_url: str = ""
    # When true, rewrite 127.0.0.1 to localhost in link base URLs for browser-friendly links.
    ovaledge_prefer_localhost_links: bool = True
    ovaledge_timeout_seconds: int = 30
    # IANA timezone sent as OvalEdge ``time-zone`` header (matches browser UI). Empty = auto-detect.
    ovaledge_client_timezone: str = ""
    # Outbound OvalEdge API: Authorization: "<scheme> <jwt>" (e.g. jwt, not Okta Bearer).
    ovaledge_http_auth_scheme: str = "jwt"
    # Log full outbound URL (method + resolved URL with query) to stderr for tracing.
    ovaledge_log_http_requests: bool = True

    # Retry config for transient OvalEdge errors
    ovaledge_max_retries: int = 3
    ovaledge_retry_backoff_seconds: float = 0.5

    # ── Auth mode ────────────────────────────────────────────────
    # "local"               → OvalEdge client_credentials flow (stdio)
    # "remote"              → Bearer OAuth access token (JWT) per request (Lambda)
    # "remote_credentials"  → X-OvalEdge-Credentials or Token + Secret per request (Lambda)
    auth_mode: Literal["local", "remote", "remote_credentials"] = "local"

    # remote_credentials only: max distinct credential-key JWT entries in memory
    credentials_cache_max_entries: int = 10_000

    # Streamable HTTP: ``True`` = POST/DELETE only per request (good for Lambda). ``False`` =
    # enables GET on ``/mcp`` for long-lived sessions — required for Cursor (and similar)
    # clients that fall back to SSE / GET after Streamable HTTP negotiation.
    mcp_http_stateless: bool = True

    # ── Local MCP — OvalEdge user token credentials ──────────────
    ovaledge_user_token: str = ""
    ovaledge_user_secret: str = ""

    # ── Remote MCP — OAuth / OIDC Authorization Server ────────────
    # Issuer base for MCP ``/.well-known/oauth-authorization-server`` proxy (login / discovery UX).
    # JWT validation uses the access token's ``iss`` for OIDC discovery (may differ on Auth0
    # custom domain vs canonical *.auth0.com).
    oauth_issuer: str = ""
    # Resource identifier expected as JWT ``aud`` (API audience).
    oauth_audience: str = ""
    mcp_public_base_url: str = ""
    aws_region: str = "us-east-1"
    # Remote only: if True, skip POST /api/user/token/generate and send the validated IdP
    # access token to OvalEdge as Authorization (see ovaledge_http_auth_scheme). If False,
    # exchange IdP token for an OvalEdge-issued JWT first (legacy).
    ovaledge_remote_forward_idp_token: bool = False

    # When create_tag omits description, MCP builds wiki HTML from tag name (+ hierarchy).
    # Set false to preserve legacy behavior (POST with no description field).
    ovaledge_tag_auto_description: bool = True

    # ── MCP server identity ──────────────────────────────────────
    mcp_server_name: str = "OvalEdge MCP Server"
    mcp_server_version: str = "0.1.0"

    @field_validator("ovaledge_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("auth_mode", mode="before")
    @classmethod
    def normalize_auth_mode(cls, v: object) -> str:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("local", "remote", "remote_credentials"):
                return s
        return v if isinstance(v, str) else "local"

_settings = Settings()


def get_settings() -> Settings:
    """Return the process-wide settings singleton (testable import boundary)."""
    return _settings


# Back-compat for existing imports.
settings = _settings


_ZONEINFO_MARKER = "zoneinfo/"


def _iana_from_etc_localtime() -> str | None:
    """Resolve IANA zone from /etc/localtime symlink (macOS/Linux)."""
    try:
        link = os.path.realpath("/etc/localtime")
    except OSError:
        return None
    idx = link.find(_ZONEINFO_MARKER)
    if idx < 0:
        return None
    zone = link[idx + len(_ZONEINFO_MARKER) :]
    if not zone:
        return None
    try:
        ZoneInfo(zone)
    except ZoneInfoNotFoundError:
        return None
    return zone


def resolve_client_timezone() -> str:
    """IANA timezone for OvalEdge ``time-zone`` header (align MCP dates with UI)."""
    configured = settings.ovaledge_client_timezone.strip()
    if configured:
        try:
            ZoneInfo(configured)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid OVALEDGE_CLIENT_TIMEZONE: {configured!r}") from exc
        return configured
    try:
        from datetime import datetime

        tzinfo = datetime.now().astimezone().tzinfo
        if tzinfo is not None:
            key = getattr(tzinfo, "key", None)
            if isinstance(key, str) and key:
                return key
    except Exception:
        pass
    from_etc = _iana_from_etc_localtime()
    if from_etc:
        return from_etc
    return "UTC"
