# Security Policy

## Supported versions

Security fixes are provided for the following release lines:

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |
| < 1.0   | No        |

The current release is declared in `pyproject.toml` (`[tool.poetry].version`).

## Reporting a vulnerability

**Do not** open a public GitHub issue for security vulnerabilities, and do not post tokens, JWTs, or OvalEdge user secrets in issues, pull requests, or discussions.

**Preferred (GitHub):** Use **private vulnerability reporting** on this repository:

1. Open the repository on GitHub.
2. Go to **Security** → **Report a vulnerability**.
3. Submit details through the private advisory form.

GitHub documents this flow in [Privately reporting a security vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability).

**Alternative:** Report through your organization’s standard security channel (security team or private ticket) if private GitHub reporting is unavailable.

### What to include

- Affected component (MCP server, auth middleware, deployment template, dependency, etc.)
- Steps to reproduce or proof of concept
- Impact assessment (confidentiality, integrity, availability)
- Suggested fix, if you have one

### What to expect

| Stage | Target |
| ----- | ------ |
| Initial acknowledgement | Within 5 business days |
| Triage and severity assessment | Within 10 business days |
| Fix or mitigation plan | Depends on severity; critical issues prioritized |

We may request additional information and will coordinate disclosure after a fix is available.

### Maintainer setup (one-time)

Repository admins should enable **Private vulnerability reporting** under **Settings** → **Security** → **Code security and analysis** so reporters can use **Security** → **Report a vulnerability**.

## Automated dependency updates

Dependabot is configured in [`.github/dependabot.yml`](.github/dependabot.yml) for:

- Python dependencies (`pyproject.toml` / `poetry.lock`)
- GitHub Actions workflows
- Docker base image (`Dockerfile`)

Review and merge Dependabot pull requests after CI passes. Regenerate `poetry.lock` locally when applying major dependency upgrades.

## Credentials and data handling

- **Never commit** `.env`, API keys, OvalEdge user tokens/secrets, or IdP client secrets. `.gitignore` excludes `.env`.
- **`remote_credentials`:** `X-OvalEdge-Credentials` and/or `X-OvalEdge-Token` / `X-OvalEdge-Secret` are sensitive. Terminate TLS at the edge (API Gateway, ALB). Do not log header values or full outbound URLs that embed secrets.
- **`remote` (OAuth WIP):** Treat Bearer tokens like secrets in transit; validate `aud` / issuer configuration before production use.

## Deployment surface

- HTTP API in `infra/template.yaml` has **no API Gateway authorizer** by design; authorization is enforced in **`AuthMiddleware`**. Add WAF, IP restrictions, or a JWT authorizer for production hardening as your risk model requires.
- Default **throttle** limits on the HTTP API reduce accidental or abusive load; tune `RouteSettings` / `DefaultRouteSettings` in the template for your traffic profile.

## Dependencies

- Lockfile: `poetry.lock` is committed. Regenerate after dependency changes and review release notes for `fastmcp`, `mcp`, `starlette`, and `httpx`.
- Run `poetry run pip audit` (or your org’s scanner) before production releases when upgrading dependencies.

## Security advisories and Dependabot alerts

- **Dependabot alerts** and **Dependabot security updates** can be enabled under **Settings** → **Security** → **Code security and analysis** (organization policy may apply).
- Published fixes for this repo appear under **Security** → **Advisories** when coordinated disclosures are released.
