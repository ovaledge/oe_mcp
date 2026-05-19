# Security

## Reporting

Report suspected vulnerabilities through your organization’s standard channel (security team or issue tracker with **private** visibility). Do not post production tokens, JWTs, or OvalEdge user secrets in public issues.

## Credentials and data handling

- **Never commit** `.env`, API keys, OvalEdge user tokens/secrets, or IdP client secrets. `.gitignore` excludes `.env`.
- **`remote_credentials`:** `X-OvalEdge-Credentials` and/or `X-OvalEdge-Token` / `X-OvalEdge-Secret` are sensitive. Terminate TLS at the edge (API Gateway, ALB). Do not log header values or full outbound URLs that embed secrets.
- **`remote` (OAuth WIP):** Treat Bearer tokens like secrets in transit; validate `aud` / issuer configuration before production use.

## Deployment surface

- HTTP API in `infra/template.yaml` has **no API Gateway authorizer** by design; authorization is enforced in **`AuthMiddleware`**. Add WAF, IP restrictions, or a JWT authorizer for production hardening as your risk model requires.
- Default **throttle** limits on the HTTP API reduce accidental or abusive load; tune `RouteSettings` / `DefaultRouteSettings` in the template for your traffic profile.

## Dependencies

- Lockfile: `poetry.lock` is committed. Regenerate after dependency changes and review release notes for `fastmcp`, `mcp`, `starlette`, and `httpx`.
