# Remote MCP — Per-User Credential Auth Plan

Design plan for a multi-user variant of the OvalEdge Remote MCP server where
each MCP client supplies its own OvalEdge `UserToken` + `UserSecret` via HTTP
headers, and the server handles JWT generation, caching, and refresh on the
user's behalf.

This is to be implemented **alongside** the existing modes, not as a replacement:

| Mode                          | Credentials                          | JWT lifetime           | Cache scope          |
| ----------------------------- | ------------------------------------ | ---------------------- | -------------------- |
| `local` (existing)            | `.env` `USER_TOKEN`+`USER_SECRET`    | refreshed by lifespan  | single process value |
| `remote` (existing OAuth)     | OAuth/OIDC Bearer access token       | per-request exchange   | none (stateless)     |
| `remote_user` (**new**)       | `X-OvalEdge-Token`+`X-OvalEdge-Secret` headers | server-managed | per-user, in-process |

---

## 1. Goals and constraints

1. **Multi-tenant**: many users hit one Remote MCP deployment; each user only
   sees what their OvalEdge JWT entitles them to (RBAC enforced server-side
   by OvalEdge — this MCP just forwards the right token).
2. **Server-managed JWT**: client never sees or caches the OvalEdge JWT. The
   client only knows its long-lived `UserToken`+`UserSecret`.
3. **Refresh policy**: regenerate the JWT 60 seconds before expiry, or
   immediately on a 401 from OvalEdge.
4. **Header-based credentials** (Option 2 from the original brief): client
   sends `X-OvalEdge-Token` + `X-OvalEdge-Secret` on every request. Server
   does not persist credentials beyond the in-memory JWT cache.
5. **Backward compatible**: existing `local` and OAuth `remote` modes keep
   working unchanged.

### Non-goals

- Replacing the OAuth `remote` mode. Both can coexist (selected by
  `AUTH_MODE`).
- Persistent (cross-process) JWT cache in v1 — see §10 for the multi-instance
  upgrade path.
- Distributing/rotating OvalEdge user tokens themselves; that's an OvalEdge
  admin concern.

---

## 2. Auth flow

```
┌────────┐      X-OvalEdge-Token + X-OvalEdge-Secret       ┌────────────┐
│ client │ ────────────────────────────────────────────►   │ MCP server │
└────────┘                                                  └─────┬──────┘
                                                                  │
                              cache hit (fresh)?                  │
                              ┌───────────────────────────────────┤
                              │                                   │
                            yes                                  no
                              │                                   │
                              │              POST /api/user/token/generate
                              │              { userToken, userSecret }
                              │                                   │
                              │                                   ▼
                              │                          OvalEdge → JWT
                              │                                   │
                              │                                   ▼
                              │                       cache[token_hash] = JWT
                              │                                   │
                              ▼                                   ▼
                          set ContextVar `current_oe_jwt` = JWT
                                            │
                                            ▼
                                    Tool calls run; OvalEdgeClient
                                    sends `Authorization: jwt <JWT>`
                                            │
                                            ▼
                                  OvalEdge 401? → invalidate that
                                                   cache entry, retry once
```

Key invariants:

- The OvalEdge JWT is **per user**, never shared.
- The cache key is derived from the user's `UserToken` (not the JWT), since
  the token is the stable identity the client sends every request.
- Cache is keyed by a **hash** of the token, never the raw value.

---

## 3. Files to add / change

| File                                            | Status | Purpose                                                                |
| ----------------------------------------------- | ------ | ---------------------------------------------------------------------- |
| `server/auth/user_cred_cache.py`                | NEW    | Per-user JWT cache with async locks, TTL eviction, max-size bound      |
| `server/auth/token_exchange.py`                 | EDIT   | Add `exchange_user_credentials(token, secret)` (parallel to existing)  |
| `server/auth/middleware.py`                     | EDIT   | Branch on `auth_mode == "remote_user"`; read headers; populate context |
| `server/auth/context.py`                        | EDIT   | (optional) add helper `set_current_oe_jwt`                             |
| `server/config.py`                              | EDIT   | Add `auth_mode == "remote_user"` validation; new tunables              |
| `server/constants.py`                           | EDIT   | Add header names + per-user leeway constant (60s)                      |
| `server/client.py`                              | EDIT   | Extend `_send_with_local_401_retry` to also handle `remote_user` mode  |
| `entrypoints/lambda_handler.py`                 | EDIT   | Doc-string only; new mode reuses the same FastAPI app                  |
| `.env.example`                                  | EDIT   | Document `AUTH_MODE=remote_user` and tunables                          |
| `tests/auth/test_user_cred_cache.py`            | NEW    | Unit tests for cache hit/miss, expiry, lock contention, eviction       |
| `tests/auth/test_middleware_remote_user.py`     | NEW    | End-to-end middleware tests with mocked OvalEdge token endpoint        |

---

## 4. Per-user JWT cache (`server/auth/user_cred_cache.py`)

### Requirements

- **Key**: `sha256(user_token)` — never store the raw token.
- **Value**: tuple `(jwt: str, exp_unix: int)`.
- **Concurrency**: per-key `asyncio.Lock` so two simultaneous requests for the
  same user collapse onto a single token-exchange call (thundering-herd
  prevention).
- **Refresh leeway**: 60 seconds (per the brief). Reuse a new constant
  `USER_CRED_REFRESH_LEEWAY_SECONDS = 60` in `server/constants.py`.
- **Eviction**: bounded LRU with max size `USER_CRED_CACHE_MAX_ENTRIES`
  (default 10_000). Drop the oldest on overflow.
- **No persistence**: process-memory only; cold start re-exchanges.
- **No raw secret retention**: the secret is only held on the stack during
  the exchange call. Never store secret in the cache value.

### Sketch

```python
# server/auth/user_cred_cache.py
import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass

from jose import jwt as jose_jwt

from server.auth.token_exchange import exchange_user_credentials
from server.constants import (
    USER_CRED_CACHE_MAX_ENTRIES,
    USER_CRED_REFRESH_LEEWAY_SECONDS,
)


@dataclass
class _Entry:
    jwt: str
    exp: int  # unix seconds; 0 == unknown (no exp claim)


class UserCredJwtCache:
    def __init__(self, max_entries: int = USER_CRED_CACHE_MAX_ENTRIES) -> None:
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._dict_lock = asyncio.Lock()
        self._max = max_entries

    @staticmethod
    def _key(user_token: str) -> str:
        return hashlib.sha256(user_token.encode()).hexdigest()

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._dict_lock:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._key_locks[key] = lock
            return lock

    def _is_fresh(self, entry: _Entry, now: int) -> bool:
        if entry.exp == 0:
            # No exp claim (opaque token) — treat as fresh for caching purposes;
            # 401 retry path will invalidate when needed.
            return True
        return entry.exp > (now + USER_CRED_REFRESH_LEEWAY_SECONDS)

    async def get_or_exchange(self, user_token: str, user_secret: str) -> str:
        key = self._key(user_token)
        now = int(time.time())

        # Fast path — cache hit, no lock needed
        entry = self._entries.get(key)
        if entry and self._is_fresh(entry, now):
            self._entries.move_to_end(key)  # LRU bump
            return entry.jwt

        # Slow path — single-flight per user
        lock = await self._lock_for(key)
        async with lock:
            entry = self._entries.get(key)
            if entry and self._is_fresh(entry, now):
                self._entries.move_to_end(key)
                return entry.jwt

            new_jwt = await exchange_user_credentials(user_token, user_secret)
            exp = self._extract_exp(new_jwt)
            self._entries[key] = _Entry(jwt=new_jwt, exp=exp)
            self._entries.move_to_end(key)
            self._evict_if_needed()
            return new_jwt

    def invalidate(self, user_token: str) -> None:
        key = self._key(user_token)
        self._entries.pop(key, None)

    def _evict_if_needed(self) -> None:
        while len(self._entries) > self._max:
            self._entries.popitem(last=False)

    @staticmethod
    def _extract_exp(token: str) -> int:
        try:
            claims = jose_jwt.get_unverified_claims(token)
        except Exception:
            return 0
        try:
            return int(claims.get("exp", 0))
        except (TypeError, ValueError):
            return 0


# Module-level singleton — Lambda warm container reuse is intentional.
user_cred_jwt_cache = UserCredJwtCache()
```

### Edge cases

- **No `exp` claim** in the JWT: treat as fresh; 401-retry path invalidates.
- **Clock skew**: 60 s leeway already covers most production skew; document
  that NTP must be healthy on the host.
- **User rotates their secret**: their old JWT is still valid until expiry.
  The cache will keep returning the still-valid JWT until OvalEdge rejects
  it; on 401 we invalidate and re-exchange with the new secret. This is
  intentional — no need to plumb secret-change signals.
- **Many distinct users** (>10k): LRU cap prevents unbounded growth. Pick the
  cap based on observed concurrency, not user-base size.

---

## 5. Token exchange (`server/auth/token_exchange.py`)

Add a new function next to `exchange_client_credentials`:

```python
async def exchange_user_credentials(user_token: str, user_secret: str) -> str:
    """
    Remote multi-user path.
    Same wire format as exchange_client_credentials, but credentials come from
    request headers rather than process env. Called via UserCredJwtCache;
    do not call directly from middleware.
    """
    async with httpx.AsyncClient(
        base_url=settings.ovaledge_base_url,
        timeout=settings.ovaledge_timeout_seconds,
    ) as client:
        response = await client.post(
            OVALEDGE_TOKEN_EXCHANGE_PATH,
            json={"userToken": user_token, "userSecret": user_secret},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if response.status_code == 401:
            raise TokenExchangeError("Invalid OvalEdge user token or secret")
        if response.status_code != 200:
            raise TokenExchangeError(
                f"OvalEdge user-cred exchange failed: "
                f"{response.status_code} {response.text}"
            )
        return _extract_token(_payload_from_token_exchange_response(response))
```

Note: keep `exchange_client_credentials` as-is — it reads from `settings`,
which is the local-mode shape. Do not unify with the new function; the
parallel pair makes the call sites obvious.

---

## 6. Middleware changes (`server/auth/middleware.py`)

Add a third branch to `dispatch`:

```python
if settings.auth_mode == "remote_user":
    if request.url.path in _UNPROTECTED:
        return await call_next(request)

    user_token = request.headers.get("X-OvalEdge-Token", "").strip()
    user_secret = request.headers.get("X-OvalEdge-Secret", "").strip()

    if not user_token or not user_secret:
        return JSONResponse(
            {
                "error": "unauthorized",
                "error_description":
                    "Missing X-OvalEdge-Token or X-OvalEdge-Secret header",
            },
            status_code=401,
        )

    try:
        oe_jwt = await user_cred_jwt_cache.get_or_exchange(user_token, user_secret)
    except TokenExchangeError as e:
        return JSONResponse(
            {"error": "invalid_credentials", "error_description": str(e)},
            status_code=401,
        )
    except Exception as e:  # network / OvalEdge upstream
        logger.warning("OvalEdge token exchange upstream failure: %s", e)
        return JSONResponse(
            {"error": "server_error", "error_description": str(e)},
            status_code=502,
        )

    current_oe_jwt.set(oe_jwt)

    # Stash token in request state so the 401-retry path in OvalEdgeClient
    # can invalidate the right cache entry without re-reading headers.
    request.state.oe_user_token = user_token
    request.state.oe_user_secret = user_secret

    return await call_next(request)
```

### 401-retry from OvalEdge

`OvalEdgeClient._send_with_local_401_retry` already retries once on 401 in
local mode by invalidating the local cache. Extend it for `remote_user`:

```python
if (
    not retried_401
    and settings.auth_mode in ("local", "remote_user")
    and response.status_code == 401
):
    if settings.auth_mode == "local":
        invalidate_local_jwt_cache()
        # re-issue local token on next loop iteration
    else:
        # remote_user: invalidate this user's cache, re-exchange, update header
        from server.auth.user_cred_cache import user_cred_jwt_cache
        from server.auth.context import current_oe_jwt
        # The cache key is the user_token we stashed in request.state, but
        # OvalEdgeClient does not have request scope. Solution: also store
        # user_token in a ContextVar (current_oe_user_token) set by middleware.
        token = current_oe_user_token.get()
        secret = current_oe_user_secret.get()
        if token and secret:
            user_cred_jwt_cache.invalidate(token)
            new_jwt = await user_cred_jwt_cache.get_or_exchange(token, secret)
            current_oe_jwt.set(new_jwt)
            self._headers["Authorization"] = _ovaledge_authorization(new_jwt)
            if self._client is not None:
                self._client.headers["Authorization"] = (
                    _ovaledge_authorization(new_jwt)
                )
    retried_401 = True
    continue
```

Add to `server/auth/context.py`:

```python
current_oe_user_token: ContextVar[str] = ContextVar("current_oe_user_token", default="")
current_oe_user_secret: ContextVar[str] = ContextVar("current_oe_user_secret", default="")
```

Middleware sets both before calling `call_next`. ContextVars are
async-task-scoped, so no cross-request leakage.

> ⚠️ Holding the user secret in a ContextVar for the duration of the request
> is the cost of being able to re-exchange on a 401. If that's unacceptable,
> the alternative is to drop the auto-retry and let the client retry with a
> fresh request — at the cost of one extra round trip on token expiry.

---

## 7. Config changes (`server/config.py`)

Extend the validator:

```python
auth_mode: Literal["local", "remote", "remote_user"] = "local"

# remote_user only: max distinct user JWTs in memory
user_cred_cache_max_entries: int = 10_000
```

`.env.example` additions:

```dotenv
# AUTH_MODE=remote_user
#   - Per-user OvalEdge token+secret in request headers
#   - X-OvalEdge-Token: <token>
#   - X-OvalEdge-Secret: <secret>
#   - Server caches the OvalEdge JWT per-user and refreshes 60s before expiry.
# AUTH_MODE=remote_user
# OVALEDGE_HTTP_AUTH_SCHEME=jwt
# USER_CRED_CACHE_MAX_ENTRIES=10000
```

Note: in `remote_user` mode the OAuth/OIDC settings (`OAUTH_ISSUER`,
`OAUTH_AUDIENCE`, `MCP_PUBLIC_BASE_URL`) are unused. Skip the discovery proxy
and `/register` — those are for OAuth `remote` only. Either:

- gate `metadata_router` and `registration_router` registration in
  `entrypoints/lambda_handler.py` on `auth_mode == "remote"`, or
- leave them mounted but have them return 404 in `remote_user` mode.

The first option is cleaner.

---

## 8. Constants (`server/constants.py`)

```python
# Header names for AUTH_MODE=remote_user.
HEADER_OE_USER_TOKEN = "X-OvalEdge-Token"
HEADER_OE_USER_SECRET = "X-OvalEdge-Secret"

# Per-user JWT cache: refresh this many seconds before expiry.
USER_CRED_REFRESH_LEEWAY_SECONDS = 60

# In-memory cap for distinct user JWT entries.
USER_CRED_CACHE_MAX_ENTRIES = 10_000
```

---

## 9. Logging and observability

- **Never** log `X-OvalEdge-Token` or `X-OvalEdge-Secret` values, full or
  truncated. Add a redaction filter to `server/logging_config.py` that masks
  these headers in any log line.
- Log the **token hash prefix** (first 8 hex chars of `sha256(token)`) when
  you need a per-user breadcrumb — that's enough to correlate without
  leaking secrets.
- Emit metrics:
  - `oe_mcp.user_cred_cache.hit`
  - `oe_mcp.user_cred_cache.miss`
  - `oe_mcp.user_cred_cache.size` (gauge)
  - `oe_mcp.token_exchange.duration_seconds`
  - `oe_mcp.token_exchange.failures`
  Use whatever the existing Lambda has wired up (CloudWatch EMF, etc.).
- Log `WARN` on 401-from-OvalEdge invalidations so we can spot credential
  rotation issues.

---

## 10. Multi-instance / Lambda concerns

The cache is **process-local**. Implications:

- Lambda concurrency N > 1 means N independent caches, each calling
  token/generate on first request. Acceptable as long as OvalEdge's
  token/generate handles the load. If not, two upgrades:
  1. **Provisioned concurrency** + warm-up pings to keep N small and warm.
  2. **Shared cache** (DynamoDB or ElastiCache). Drop-in replace
     `UserCredJwtCache` with the same interface; the rest of the codebase
     does not change. Default TTL = `JWT exp - 60s`. Use `sha256(token)` as
     the partition key. Encrypt at rest (KMS).
- Cold starts: first request per user takes one extra round trip. Document
  this so MCP clients know to expect ~200ms higher first-request latency.

---

## 11. Security checklist

- [ ] Reject requests without HTTPS in production (API Gateway / ALB level).
- [ ] Both headers required; never accept one without the other.
- [ ] Trim headers; reject if they contain whitespace mid-value.
- [ ] Length-bound headers (e.g. ≤2 KiB each) before any work.
- [ ] Hash before using as cache key; never index on raw token.
- [ ] Logging filter strips `X-OvalEdge-*` and `Authorization` from access logs.
- [ ] On any auth failure, return generic `invalid_credentials` — do not echo
      OvalEdge's internal error text to the client unless safe.
- [ ] Document that the MCP server now sees plaintext OvalEdge user
      credentials in headers; if customers consider that unacceptable, fall
      back to OAuth `remote` mode.

---

## 12. Testing plan

### Unit tests (new)

- `tests/auth/test_user_cred_cache.py`
  - cache miss → calls `exchange_user_credentials` exactly once
  - cache hit (within leeway) → no exchange call
  - cache near-expiry (within 60 s) → exchange called again
  - 100 concurrent calls for same user → single exchange call
    (thundering-herd test)
  - LRU eviction at `max_entries + 1`
  - `invalidate(token)` removes the entry
  - JWT with no `exp` is treated as fresh until invalidated

- `tests/auth/test_token_exchange_user.py`
  - mocked OvalEdge 200 with `{token: ...}` → returns token
  - mocked 401 → raises `TokenExchangeError`
  - mocked 5xx → raises `TokenExchangeError`

### Integration tests (new)

- `tests/auth/test_middleware_remote_user.py`
  - Missing both headers → 401
  - Missing one of two headers → 401
  - Valid headers, mocked OvalEdge → 200, ContextVar populated
  - Invalid creds, mocked 401 from OvalEdge → 401 from MCP
  - Two requests, same user → second hits the cache (assert single
    upstream call)
  - Two requests, different users → both miss, both populate cache

### Existing tests

- Confirm `auth_mode=local` and `auth_mode=remote` paths still pass without
  modification. Add a fixture parametrization on `auth_mode`.

---

## 13. Rollout

1. Land cache + token-exchange function + tests; no behavior change yet.
2. Land middleware branch; gated by `AUTH_MODE=remote_user`. Ship to a
   non-prod stack.
3. Smoke test with two users from different orgs against the OvalEdge
   sandbox. Confirm RBAC isolation (User A cannot see User B's assets).
4. Run a load test: 50 RPS sustained with 100 distinct users. Verify cache
   hit ratio >95% and token-exchange latency p95 <500 ms.
5. Decide single-instance vs DynamoDB-backed cache before production cutover.
6. Update README with `AUTH_MODE=remote_user` section and an example client
   request.

---

## 14. Open questions to confirm before implementation

1. **Same exchange endpoint?** `exchange_client_credentials` posts
   `{userToken, userSecret}` to `/api/user/token/generate`. Confirm this
   endpoint is the right one for end-user credentials, not just service
   accounts.
2. **JWT lifetime**: what does OvalEdge currently issue? If <2 minutes, the
   60 s leeway leaves a thin window — consider 30 s or push OvalEdge to
   issue longer-lived tokens.
3. **Rate limits** on `/api/user/token/generate`: any per-user cap that
   would make our cache TTL too aggressive on cold starts?
4. **Audit log**: does OvalEdge log JWT generation events? If yes, our
   refresh cadence will show up — confirm SOC team is OK with one
   refresh per (user, ~JWT lifetime).
5. **Can the secret be omitted on refresh?** Some systems support a
   refresh-token grant. If so, drop secret retention entirely and store
   only a refresh token in the cache.

Resolve these before starting on §4 and §5.
