"""
Opaque in-process cache keys derived from sensitive auth material.

These digests are **lookup keys** for JWT / validation caches — never password
storage, never verification of user-supplied passwords. CodeQL's
``py/weak-sensitive-data-hashing`` query often misclassifies tokens/secrets as
"password"; we use a keyed HMAC fingerprint and suppress that rule at the
single call site below.
"""

from __future__ import annotations

import hashlib
import hmac

# App-local pepper so cache keys are keyed MACs (not bare digests of tokens).
# Not a deploy secret: rotating it only invalidates in-process cache entries.
_CACHE_KEY_PEPPER = b"oe-mcp/v1/auth-cache-key"


def opaque_cache_key(*parts: str) -> str:
    """
    Return a stable hex fingerprint of ``parts`` for LRU cache addressing.

    Not suitable for password hashing / credential storage. Use Argon2/bcrypt
    (or the IdP) for that.
    """
    # codeql[py/weak-sensitive-data-hashing]: opaque cache addressing only;
    # not password hashing or password verification (HMAC fingerprint for LRU keys).
    mac = hmac.new(_CACHE_KEY_PEPPER, digestmod=hashlib.sha256)
    for i, part in enumerate(parts):
        if i:
            mac.update(b"\0")
        mac.update(part.encode("utf-8"))
    return mac.hexdigest()
