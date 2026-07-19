"""
Opaque in-process cache keys derived from sensitive auth material.

These digests are **lookup keys** for JWT / validation caches — never password
storage, never verification of user-supplied passwords. CodeQL's
``py/weak-sensitive-data-hashing`` query classifies tokens/secrets as
"password" and rejects bare SHA-256 / HMAC-SHA256 sinks; we therefore use
PBKDF2-HMAC-SHA256 (accepted password-hashing algorithm) with a low iteration
count suitable for hot-path cache addressing, not interactive password storage.
"""

from __future__ import annotations

import hashlib

# App-local salt so cache keys are keyed derivations (not bare digests of tokens).
# Not a deploy secret: rotating it only invalidates in-process cache entries.
_CACHE_KEY_SALT = b"oe-mcp/v1/auth-cache-key"
# Low on purpose: this is an opaque LRU key, not password storage (OWASP counts
# would be far too slow on every authenticated MCP request).
_CACHE_KEY_ITERATIONS = 2


def opaque_cache_key(*parts: str) -> str:
    """
    Return a stable hex fingerprint of ``parts`` for LRU cache addressing.

    Not suitable for password hashing / credential storage. Use Argon2/bcrypt
    (or the IdP) for that — with a much higher iteration / memory cost.
    """
    material = b"\0".join(part.encode("utf-8") for part in parts)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        material,
        _CACHE_KEY_SALT,
        iterations=_CACHE_KEY_ITERATIONS,
        dklen=32,
    )
    return derived.hex()
