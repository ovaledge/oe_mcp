from typing import Any

from fastapi import APIRouter, HTTPException

from server.auth.oauth_discovery import OAuthDiscoveryError, get_authorization_server_metadata
from server.config import settings

router = APIRouter()


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata() -> dict[str, Any]:
    """
    RFC 8414 OAuth 2.0 Authorization Server Metadata (proxy).

    Loads the IdP's OIDC or OAuth AS discovery document using ``oauth_issuer``,
    then re-exposes endpoints so MCP clients can follow OAuth without hardcoding a vendor.
    Token and authorization calls go to the IdP; this host only adds ``registration_endpoint``.
    """
    try:
        doc = await get_authorization_server_metadata()
    except OAuthDiscoveryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    registration = f"{settings.mcp_public_base_url.rstrip('/')}/register"
    return {
        "issuer": doc["issuer"],
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
        "token_endpoint_auth_methods_supported": doc.get("token_endpoint_auth_methods_supported")
        if isinstance(doc.get("token_endpoint_auth_methods_supported"), list)
        else ["none"],
        "scopes_supported": doc.get("scopes_supported")
        if isinstance(doc.get("scopes_supported"), list)
        else ["openid", "email", "profile"],
    }
