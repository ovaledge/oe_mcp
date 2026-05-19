"""
RFC 8414 / RFC 9728 discovery stubs for ``AUTH_MODE=remote_credentials``.

MCP HTTP clients (including Cursor) probe ``/.well-known/oauth-*`` before Streamable HTTP.
Without these routes, FastAPI returns ``{"detail":"Not Found"}``, which some clients misparse
as an OAuth error. OAuth is **not** used in this mode; clients must send
``X-OvalEdge-Credentials`` (``token::secret``) or ``X-OvalEdge-Token`` / ``X-OvalEdge-Secret`` on ``POST /mcp``.

The metadata points ``authorization_endpoint`` / ``token_endpoint`` at ``/mcp-auth/declined``,
which returns a standard OAuth 2.0 error JSON (400) if hit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["remote-credentials-discovery"])


def _public_base(request: Request) -> str:
    """Scheme + host (+ port) only, no trailing slash."""
    return str(request.base_url).rstrip("/")


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata(request: Request) -> dict[str, Any]:
    """RFC 8414 AS metadata — satisfies discovery; OAuth browser flow is not used."""
    base = _public_base(request)
    declined = f"{base}/mcp-auth/declined"
    return {
        "issuer": base,
        "authorization_endpoint": declined,
        "token_endpoint": declined,
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": [],
    }


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request) -> dict[str, Any]:
    """Minimal OIDC discovery for clients that try openid-configuration after OAuth AS."""
    base = _public_base(request)
    declined = f"{base}/mcp-auth/declined"
    return {
        "issuer": base,
        "authorization_endpoint": declined,
        "token_endpoint": declined,
        "jwks_uri": declined,
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata_root(request: Request) -> dict[str, Any]:
    """RFC 9728 — root fallback when resource path is unknown."""
    base = _public_base(request)
    mcp_url = f"{base}/mcp"
    return {
        "resource": mcp_url,
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    }


@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_metadata_mcp(request: Request) -> dict[str, Any]:
    """RFC 9728 path-aware document for MCP resource ``/mcp``."""
    base = _public_base(request)
    mcp_url = f"{base}/mcp"
    return {
        "resource": mcp_url,
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    }


@router.api_route("/mcp-auth/declined", methods=["GET", "POST", "OPTIONS"])
async def oauth_declined_stub() -> JSONResponse:
    """Placeholder AS endpoints — OAuth is not enabled in remote_credentials mode."""
    return JSONResponse(
        {
            "error": "unsupported_grant_type",
            "error_description": (
                "This deployment uses AUTH_MODE=remote_credentials. "
                "Send X-OvalEdge-Credentials (token::secret) or X-OvalEdge-Token and "
                "X-OvalEdge-Secret on MCP HTTP requests instead of OAuth."
            ),
        },
        status_code=400,
    )
