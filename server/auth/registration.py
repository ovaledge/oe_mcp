import secrets
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# In-memory store — acceptable for stateless Lambda.
# Clients re-register on cold start. Idempotent by design.
#
# KNOWN LIMITATION: registrations are lost on Lambda cold start.
# MCP clients MUST handle re-registration gracefully.
# For durable registration, replace with DynamoDB:
#   import boto3
#   _table = boto3.resource("dynamodb").Table("mcp-client-registrations")
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
    RFC 7591 Dynamic Client Registration.
    MCP clients call this before starting the OAuth flow.
    Returns a client_id used in the Okta authorization request.

    Security note: this endpoint is open by design for MCP compliance.
    Restrict via API Gateway throttling to prevent abuse.
    """
    client_id = secrets.token_urlsafe(16)
    _registered_clients[client_id] = request.model_dump()
    return {
        "client_id": client_id,
        "client_name": request.client_name,
        "redirect_uris": request.redirect_uris,
        "grant_types": request.grant_types,
        "response_types": request.response_types,
        "token_endpoint_auth_method": request.token_endpoint_auth_method,
    }
