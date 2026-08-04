"""joserfc-backed JWT helpers (replacing python-jose)."""

from __future__ import annotations

import time

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey

from server.auth.jwt_util import decode_rs_jwt, encode_hs256, get_unverified_claims


def test_get_unverified_claims_and_encode_hs256() -> None:
    token = encode_hs256({"sub": "u", "exp": int(time.time()) + 60})
    claims = get_unverified_claims(token)
    assert claims["sub"] == "u"
    assert isinstance(claims["exp"], int)


def test_decode_rs_jwt_validates_iss_and_aud() -> None:
    key = RSAKey.generate_key(2048)
    claims = {
        "iss": "https://idp.example.com",
        "aud": ["api://my-api", "other"],
        "sub": "user-1",
        "exp": int(time.time()) + 120,
    }
    token = jwt.encode({"alg": "RS256"}, claims, key)
    jwks = {"keys": [key.as_dict(private=False)]}

    out = decode_rs_jwt(
        token,
        jwks,
        issuer="https://idp.example.com",
        audience="api://my-api",
    )
    assert out["sub"] == "user-1"

    with pytest.raises(Exception):
        decode_rs_jwt(
            token,
            jwks,
            issuer="https://wrong.example.com",
            audience="api://my-api",
        )
