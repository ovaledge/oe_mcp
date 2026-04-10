from typing import Any

from fastapi import APIRouter

from server.config import settings

router = APIRouter()


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata() -> dict[str, Any]:
    """
    RFC 8414 OAuth 2.0 Authorization Server Metadata.
    MCP client reads this first to discover Okta endpoints.
    authorization_endpoint and token_endpoint point directly at Okta —
    the Lambda is never in the token issuance path.
    """
    okta_base = f"{settings.okta_domain}/oauth2/{settings.okta_auth_server_id}"
    return {
        "issuer": okta_base,
        "authorization_endpoint": f"{okta_base}/v1/authorize",
        "token_endpoint": f"{okta_base}/v1/token",
        "jwks_uri": f"{okta_base}/v1/keys",
        "registration_endpoint": f"{settings.mcp_public_base_url}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["openid", "email", "profile"],
    }
