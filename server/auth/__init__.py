"""
Authentication for local stdio and remote HTTP MCP.

- ``context`` — per-request JWT ContextVar
- ``token_exchange`` — local client_credentials / remote IdP exchange
- ``middleware`` — FastAPI auth for remote entrypoints
- ``bearer_jwt`` / ``oauth_discovery`` — remote OAuth validation
- ``credentials_cache`` / ``remote_credentials_*`` — per-user token+secret mode
"""
