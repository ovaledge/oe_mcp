"""
OvalEdge MCP tool domains.

Each package exposes ``register(mcp)`` and optional ``helpers`` / ``formatters`` modules:

- ``catalog`` — asset explorer/details/lineage, metadata drift, descriptions
- ``governance`` — glossary/tag creates, governance roles, custom fields
- ``servicedesk`` — service request template lookup and create
- ``dataquality`` — CDE assessment, DQ rules, custom SQL generate/validate/create
- ``docs`` — knowledge_search (data stories + platform docs)
- ``rdam`` — native Redshift/Snowflake/Tableau access (source-system grants)
- ``common`` — shared params, errors, validators, client factory
"""

from server.tools import access, catalog, dataquality, docs, governance, rdam, servicedesk

__all__ = ["access", "catalog", "dataquality", "docs", "governance", "rdam", "servicedesk"]
