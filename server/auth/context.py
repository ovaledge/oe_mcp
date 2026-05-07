from contextvars import ContextVar

# Holds the OvalEdge JWT for the current request.
# Set by auth middleware (remote) or lifespan hook (local) before tools run.
# Read by OvalEdgeClient on instantiation.
# ContextVar is async-safe — no cross-request leakage.
current_oe_jwt: ContextVar[str] = ContextVar("current_oe_jwt", default="")

# AUTH_MODE=remote_credentials — SHA-256 cache key for OvalEdge JWT cache (never raw token/secret).
current_oe_credential_cache_key: ContextVar[str] = ContextVar(
    "current_oe_credential_cache_key",
    default="",
)

# AUTH_MODE=remote_credentials — OvalEdge ``token/generate`` inputs for this request only.
# Set with the JWT after successful exchange; read to refresh JWT when OvalEdge invalidates session.
# Never log — same sensitivity as inbound credential headers.
current_oe_user_token: ContextVar[str] = ContextVar("current_oe_user_token", default="")
current_oe_user_secret: ContextVar[str] = ContextVar("current_oe_user_secret", default="")

# Local mode process cache (server-side only).
# This is not browser localStorage/sessionStorage.
local_cached_oe_jwt: str = ""
