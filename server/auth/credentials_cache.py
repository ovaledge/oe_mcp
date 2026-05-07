"""
Per-user OvalEdge JWT cache for ``AUTH_MODE=remote_credentials``.

In-memory default; ``CredentialsCacheBackend`` allows swapping in DynamoDB / Redis later.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from server.constants import (
    CREDENTIALS_CACHE_MAX_ENTRIES,
    CREDENTIALS_CACHE_POST_EXP_GRACE_SECONDS,
    NEGATIVE_CREDENTIALS_CACHE_MAX_ENTRIES,
    NEGATIVE_CREDENTIALS_CACHE_TTL_SECONDS,
)


def credential_cache_key(user_token: str, user_secret: str) -> str:
    """Stable cache key; never log — derived from digested material only."""
    h = hashlib.sha256()
    h.update(user_token.encode("utf-8"))
    h.update(b":")
    h.update(user_secret.encode("utf-8"))
    return h.hexdigest()


@dataclass(frozen=True)
class CachedJwtEntry:
    jwt: str
    exp_epoch: int  # 0 if no exp claim


@runtime_checkable
class CredentialsCacheBackend(Protocol):
    """Pluggable store for user-credential JWT cache (in-memory or shared)."""

    async def get_entry(self, key: str) -> CachedJwtEntry | None:
        ...

    async def set_entry(self, key: str, entry: CachedJwtEntry) -> None:
        ...

    async def delete_entry(self, key: str) -> None:
        ...

    def refresh_lock(self, key: str) -> AbstractAsyncContextManager[None]:
        ...


class InMemoryCredentialsCache:
    """
    LRU-bound in-process cache. TTL: entries past ``exp + grace`` are treated as absent.

    One ``asyncio.Lock`` per key prevents concurrent token/generate stampedes.
    """

    def __init__(
        self,
        *,
        max_entries: int = CREDENTIALS_CACHE_MAX_ENTRIES,
        post_exp_grace_seconds: int = CREDENTIALS_CACHE_POST_EXP_GRACE_SECONDS,
    ) -> None:
        self._max_entries = max_entries
        self._post_exp_grace = post_exp_grace_seconds
        self._entries: OrderedDict[str, CachedJwtEntry] = OrderedDict()
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._structure_lock = asyncio.Lock()

    def _lock_for_key(self, key: str) -> asyncio.Lock:
        return self._key_locks.setdefault(key, asyncio.Lock())

    def _evict_lru_if_needed_unlocked(self) -> None:
        while len(self._entries) > self._max_entries:
            old_key, _ = self._entries.popitem(last=False)
            self._key_locks.pop(old_key, None)

    def _is_past_ttl(self, now: int, entry: CachedJwtEntry) -> bool:
        if entry.exp_epoch <= 0:
            return False
        return now > entry.exp_epoch + self._post_exp_grace

    async def get_entry(self, key: str) -> CachedJwtEntry | None:
        now = int(time.time())
        async with self._structure_lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if self._is_past_ttl(now, entry):
                del self._entries[key]
                self._key_locks.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return entry

    async def set_entry(self, key: str, entry: CachedJwtEntry) -> None:
        async with self._structure_lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            self._evict_lru_if_needed_unlocked()

    async def delete_entry(self, key: str) -> None:
        async with self._structure_lock:
            self._entries.pop(key, None)
            self._key_locks.pop(key, None)

    @asynccontextmanager
    async def refresh_lock(self, key: str) -> AsyncIterator[None]:
        lock = self._lock_for_key(key)
        async with lock:
            yield

    def clear_all(self) -> None:
        """Test helper: drop all state."""
        self._entries.clear()
        self._key_locks.clear()


class InMemoryNegativeCredentialsCache:
    """
    Short-lived blocklist for credential keys that recently failed token/generate with 401.

    Reduces repeated upstream calls from misconfigured or abusive clients while keeping TTL
    low so legitimate credential rotation is not delayed long.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = NEGATIVE_CREDENTIALS_CACHE_TTL_SECONDS,
        max_entries: int = NEGATIVE_CREDENTIALS_CACHE_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._until: OrderedDict[str, int] = OrderedDict()
        self._structure_lock = asyncio.Lock()

    def _purge_expired_unlocked(self, now: int) -> None:
        stale = [k for k, exp in self._until.items() if now >= exp]
        for k in stale:
            del self._until[k]

    async def is_blocked(self, key: str) -> bool:
        now = int(time.time())
        async with self._structure_lock:
            self._purge_expired_unlocked(now)
            exp = self._until.get(key)
            if exp is None:
                return False
            if now >= exp:
                del self._until[key]
                return False
            self._until.move_to_end(key)
            return True

    async def mark_blocked(self, key: str) -> None:
        now = int(time.time())
        expiry = now + self._ttl
        async with self._structure_lock:
            self._purge_expired_unlocked(now)
            self._until[key] = expiry
            self._until.move_to_end(key)
            while len(self._until) > self._max_entries:
                self._until.popitem(last=False)

    async def forget(self, key: str) -> None:
        async with self._structure_lock:
            self._until.pop(key, None)

    def clear_all(self) -> None:
        self._until.clear()


_default_credentials_cache: InMemoryCredentialsCache | None = None
_default_negative_credentials_cache: InMemoryNegativeCredentialsCache | None = None


def get_default_credentials_cache() -> InMemoryCredentialsCache:
    global _default_credentials_cache
    if _default_credentials_cache is None:
        from server.config import settings

        _default_credentials_cache = InMemoryCredentialsCache(
            max_entries=settings.credentials_cache_max_entries,
        )
    return _default_credentials_cache


def get_default_negative_credentials_cache() -> InMemoryNegativeCredentialsCache:
    global _default_negative_credentials_cache
    if _default_negative_credentials_cache is None:
        _default_negative_credentials_cache = InMemoryNegativeCredentialsCache(
            ttl_seconds=NEGATIVE_CREDENTIALS_CACHE_TTL_SECONDS,
            max_entries=NEGATIVE_CREDENTIALS_CACHE_MAX_ENTRIES,
        )
    return _default_negative_credentials_cache


def reset_default_negative_credentials_cache() -> None:
    """Test helper: next ``get_default_negative_credentials_cache()`` starts empty."""
    global _default_negative_credentials_cache
    if _default_negative_credentials_cache is not None:
        _default_negative_credentials_cache.clear_all()
    _default_negative_credentials_cache = None


def reset_default_credentials_cache() -> None:
    """Test helper: next ``get_default_credentials_cache()`` starts empty."""
    global _default_credentials_cache
    if _default_credentials_cache is not None:
        _default_credentials_cache.clear_all()
    _default_credentials_cache = None
    reset_default_negative_credentials_cache()
