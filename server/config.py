from pathlib import Path

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
    ovaledge_timeout_seconds: int = 30
    # Outbound OvalEdge API: Authorization: "<scheme> <jwt>" (e.g. jwt, not Okta Bearer).
    ovaledge_http_auth_scheme: str = "jwt"
    # Log full outbound URL (method + resolved URL with query) to stderr for tracing.
    ovaledge_log_http_requests: bool = True

    # Retry config for transient OvalEdge errors
    ovaledge_max_retries: int = 3
    ovaledge_retry_backoff_seconds: float = 0.5

    # ── Auth mode ────────────────────────────────────────────────
    # "local"  → OvalEdge client_credentials flow (stdio)
    # "remote" → Okta OAuth 2.1 PKCE flow (Lambda)
    auth_mode: str = "local"

    # ── Local MCP — OvalEdge user token credentials ──────────────
    ovaledge_user_token: str = ""
    ovaledge_user_secret: str = ""

    # ── Remote MCP — Okta custom auth server ────────────────────
    okta_domain: str = ""
    okta_auth_server_id: str = ""
    okta_client_id: str = ""
    okta_audience: str = ""
    mcp_public_base_url: str = ""
    aws_region: str = "us-east-1"

    # ── MCP server identity ──────────────────────────────────────
    mcp_server_name: str = "OvalEdge MCP Server"
    mcp_server_version: str = "0.1.0"

    @field_validator("ovaledge_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


settings = Settings()
