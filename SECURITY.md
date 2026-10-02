# Security Policy

## Supported versions

Security fixes are provided for the following release lines:

| Version | Supported |
| ------- | --------- |
| 2.0.x   | Yes       |
| 1.0.x   | No        |
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

## Code scanning (CodeQL)

- **Local (every commit):** pre-commit runs `scripts/run_codeql.sh` (CLI required by default). Install with `./scripts/install_codeql_cli.sh`.
- **CI (advanced setup):** [`.github/workflows/codeql.yml`](.github/workflows/codeql.yml) analyzes Python on PRs and pushes to `main`/`dev` using [`.github/codeql/codeql-config.yml`](.github/codeql/codeql-config.yml).
- **Disable CodeQL default setup** in **Settings → Code security → Code scanning** when using this workflow. Running default + advanced together often produces the PR check *Code scanning results / CodeQL* failing in a few seconds with *Error when processing the SARIF file*.
- Findings such as `py/weak-sensitive-data-hashing` should be fixed or justified before merge; do not rely on post-merge Security-tab discovery alone.

## Automated dependency updates

Dependabot is configured in [`.github/dependabot.yml`](.github/dependabot.yml) for:

- Python dependencies (`pyproject.toml` / `poetry.lock`)
- GitHub Actions workflows
- Docker base image (`Dockerfile`)

Review and merge Dependabot pull requests after CI passes. Regenerate `poetry.lock` locally when applying major dependency upgrades.
