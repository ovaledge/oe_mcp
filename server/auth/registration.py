import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.config import settings

router = APIRouter()

# Optional audit of who called DCR. Authorize always uses configured OAUTH_CLIENT_ID —
# Okta (and most IdPs) reject random client_ids from local DCR.
_registered_clients: dict[str, dict[str, Any]] = {}


class ClientRegistrationRequest(BaseModel):
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str] = ["authorization_code"]
    response_types: list[str] = ["code"]
    token_endpoint_auth_method: str = "none"


@router.post("/register")
async def register_client(request: ClientRegistrationRequest) -> dict[str, Any]:
    """
    RFC 7591 Dynamic Client Registration (MCP-facing).

    Returns the **pre-registered** IdP ``OAUTH_CLIENT_ID`` so authorize/token
    calls succeed against Okta. MCP does not mint Okta apps.

    When ``OAUTH_CLIENT_SECRET`` is set (confidential Okta Web app), the response
    includes ``client_secret`` and ``token_endpoint_auth_method=client_secret_post``
    so MCP clients can complete the token exchange. Prefer a public Native/SPA app
    (PKCE, no secret) for production MCP if you do not want the secret returned here.
    """
    client_id = (settings.oauth_client_id or "").strip()
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "OAUTH_CLIENT_ID is not set. Create an Okta OIDC app (PKCE) for MCP "
                "clients and set OAUTH_CLIENT_ID on this server."
            ),
        )

    client_secret = (settings.oauth_client_secret or "").strip()
    # Confidential Okta apps reject token exchange with auth_method=none.
    if client_secret:
        token_auth = "client_secret_post"
    else:
        token_auth = request.token_endpoint_auth_method or "none"

    audit_key = secrets.token_urlsafe(8)
    _registered_clients[audit_key] = {
        **request.model_dump(),
        "client_id": client_id,
        "token_endpoint_auth_method": token_auth,
        "registered_at": int(time.time()),
    }

    scopes = " ".join(
        part for part in (settings.oauth_scopes or "").replace(",", " ").split() if part
    )
    body: dict[str, Any] = {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "client_name": request.client_name,
        "redirect_uris": request.redirect_uris,
        "grant_types": request.grant_types,
        "response_types": request.response_types,
        "token_endpoint_auth_method": token_auth,
    }
    if client_secret:
        body["client_secret"] = client_secret
    if scopes:
        body["scope"] = scopes
    return body
