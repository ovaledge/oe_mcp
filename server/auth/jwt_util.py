"""
JWT helpers backed by ``joserfc`` (replaces ``python-jose``).

``python-jose`` pulled in unmaintained ``ecdsa``; ``joserfc`` uses ``cryptography``.
"""

from __future__ import annotations

import json
from typing import Any, cast

from joserfc import jws, jwt
from joserfc.jwk import KeySet, OctKey
from joserfc.jwt import JWTClaimsRegistry

# Default algorithms for IdP access-token JWKS verification (Okta / OIDC RS*).
DEFAULT_RS_ALGORITHMS: tuple[str, ...] = ("RS256", "RS384", "RS512")


def get_unverified_claims(token: str) -> dict[str, Any]:
    """Return JWT payload claims without verifying the signature."""
    obj = jws.extract_compact(token.encode("utf-8"))
    payload = obj.payload
    if isinstance(payload, bytes):
        payload_text = payload.decode("utf-8")
    else:
        payload_text = str(payload)
    claims = json.loads(payload_text)
    if not isinstance(claims, dict):
        raise ValueError("JWT payload is not a JSON object")
    return claims


def decode_rs_jwt(
    token: str,
    jwks: dict[str, Any],
    *,
    issuer: str,
    algorithms: list[str] | tuple[str, ...] = DEFAULT_RS_ALGORITHMS,
    audience: str | None = None,
) -> dict[str, Any]:
    """
    Verify an RS* JWT against a JWKS document and validate ``iss`` / optional ``aud``.

    ``audience`` matches python-jose behavior: required when set; accepts a string
    ``aud`` claim or a list that contains the expected audience.
    """
    # JWKS HTTP JSON is a plain dict; joserfc types it as KeySetSerialization.
    key_set = KeySet.import_key_set(cast(Any, jwks))
    token_obj = jwt.decode(token, key_set, algorithms=list(algorithms))
    claims_options: dict[str, Any] = {
        "iss": {"essential": True, "value": issuer},
    }
    if audience:
        claims_options["aud"] = {"essential": True, "value": audience}
    JWTClaimsRegistry(**claims_options).validate(token_obj.claims)
    return dict(token_obj.claims)


def encode_hs256(claims: dict[str, Any], secret: str = "test-secret-key-112bits-min") -> str:
    """Encode a compact HS256 JWT (tests / local fixtures only)."""
    key = OctKey.import_key(secret)
    return jwt.encode({"alg": "HS256"}, claims, key)
