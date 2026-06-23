"""
OvalEdge MCP tool domains.

Each package exposes ``register(mcp)`` and optional ``helpers`` / ``formatters`` modules:

- ``catalog`` — search, details, lineage, metadata drift, descriptions
- ``governance`` — glossary, tags, data stories, governance roles
- ``dataquality`` — CDE assessment, DQ rule lookup, associate, create
- ``docs`` — platform documentation semantic search
- ``rdam`` — native Redshift/Snowflake/Tableau access (source-system grants)
- ``common`` — shared params, errors, validators, client factory
"""

from server.tools import access, catalog, dataquality, docs, governance, rdam

__all__ = ["access", "catalog", "dataquality", "docs", "governance", "rdam"]
