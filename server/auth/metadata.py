from typing import Any

from fastapi import APIRouter, HTTPException, Request

from server.auth.oauth_discovery import OAuthDiscoveryError, get_authorization_server_metadata
from server.config import settings

router = APIRouter()


def _mcp_public_origin(request: Request) -> str:
    """RFC 8414 ``registration_endpoint`` must be absolute. Prefer setting; else request URL."""
    configured = (settings.mcp_public_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def _configured_scopes(doc: dict[str, Any]) -> list[str]:
    from_idp = doc.get("scopes_supported")
    if isinstance(from_idp, list) and from_idp:
        return [str(s) for s in from_idp]
    return [part for part in (settings.oauth_scopes or "").replace(",", " ").split() if part]


def _authorization_server_metadata_payload(
    request: Request, doc: dict[str, Any]
) -> dict[str, Any]:
    """
    Build AS metadata for MCP clients.

    ``issuer`` and ``registration_endpoint`` are this MCP host so clients do **not**
    follow Okta's issuer and attempt Okta Dynamic Client Registration (which returns
    non-RFC errors like E0000005 Invalid session). Authorize/token/JWKS stay on the IdP.
    """
    origin = _mcp_public_origin(request)
    registration = f"{origin}/register"
    # Prefer IdP's token_endpoint_auth_methods but ensure public PKCE clients work.
    # When OAUTH_CLIENT_SECRET is set, advertise confidential methods too (Okta Web apps).
    token_auth = doc.get("token_endpoint_auth_methods_supported")
    if not isinstance(token_auth, list) or not token_auth:
        token_auth = ["none"]
    else:
        token_auth = list(token_auth)
    if "none" not in token_auth:
        token_auth.append("none")
    if (settings.oauth_client_secret or "").strip():
        for method in ("client_secret_post", "client_secret_basic"):
            if method not in token_auth:
                token_auth.append(method)

    return {
        # MCP origin (not Okta) — stops clients from re-discovering Okta and calling Okta DCR.
        "issuer": origin,
        "authorization_endpoint": doc["authorization_endpoint"],
        "token_endpoint": doc["token_endpoint"],
        "jwks_uri": doc["jwks_uri"],
        "registration_endpoint": registration,
        "response_types_supported": doc.get("response_types_supported")
        if isinstance(doc.get("response_types_supported"), list)
        else ["code"],
        "grant_types_supported": doc.get("grant_types_supported")
        if isinstance(doc.get("grant_types_supported"), list)
        else ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": doc.get("code_challenge_methods_supported")
        if isinstance(doc.get("code_challenge_methods_supported"), list)
        else ["S256"],
        "token_endpoint_auth_methods_supported": token_auth,
        "scopes_supported": _configured_scopes(doc),
    }


async def _load_idp_metadata() -> dict[str, Any]:
    try:
        return await get_authorization_server_metadata()
    except OAuthDiscoveryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request) -> dict[str, Any]:
    """
    RFC 8414 OAuth 2.0 Authorization Server Metadata (proxy).

    Loads the IdP discovery document, keeps authorize/token/JWKS on the IdP, and
    advertises this host as ``issuer`` + ``registration_endpoint`` for MCP clients.
    """
    doc = await _load_idp_metadata()
    return _authorization_server_metadata_payload(request, doc)


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request) -> dict[str, Any]:
    """OIDC discovery for clients that probe openid-configuration on the MCP host."""
    doc = await _load_idp_metadata()
    payload = _authorization_server_metadata_payload(request, doc)
    payload.setdefault("subject_types_supported", ["public"])
    payload.setdefault("id_token_signing_alg_values_supported", ["RS256"])
    return payload


def _protected_resource_payload(request: Request) -> dict[str, Any]:
    origin = _mcp_public_origin(request)
    mcp_url = f"{origin}/mcp"
    # Point at this MCP host so clients load *our* AS metadata (with /register), not Okta DCR.
    return {
        "resource": mcp_url,
        "authorization_servers": [origin],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [
            part for part in (settings.oauth_scopes or "").replace(",", " ").split() if part
        ],
    }


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata_root(request: Request) -> dict[str, Any]:
    """RFC 9728 — root fallback when resource path is unknown."""
    return _protected_resource_payload(request)


@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_metadata_mcp(request: Request) -> dict[str, Any]:
    """RFC 9728 path-aware document for MCP resource ``/mcp``."""
    return _protected_resource_payload(request)
