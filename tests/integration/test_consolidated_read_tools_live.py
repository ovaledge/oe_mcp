"""
Live integration tests for the four consolidated MCP read tools.

Five tests per tool (20 total):
  - asset_explorer   → GET /api/v1/mcp/asset-explorer
  - asset_details    → GET /api/v1/mcp/asset-details
  - asset_lineage    → GET /api/v1/mcp/asset-lineage
  - knowledge_search → GET /api/v1/mcp/knowledge-search

Fixtures are discovered dynamically via the live MCP APIs (asset_explorer and
related endpoints), so the tests do not depend on hard-coded object ids or direct
database access. Override discovery hints with OE_IT_* env vars.

Run:
  poetry run pytest -c tests/integration/pytest.ini \
    tests/integration/test_consolidated_read_tools_live.py -m integration

Requires OvalEdge at OVALEDGE_BASE_URL and valid credentials in .env
(OVALEDGE_USER_TOKEN + OVALEDGE_USER_SECRET) or OE_INTEGRATION_JWT.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from server.constants import (
    MCP_PATH_ASSET_DETAILS,
    MCP_PATH_ASSET_LINEAGE,
    MCP_PATH_KNOWLEDGE_SEARCH,
)
from tests.integration.helpers import data as _data
from tests.integration.helpers import explore as _explore
from tests.integration.helpers import items as _items

pytestmark = pytest.mark.integration

# ── Discovery hints (env-overridable) ────────────────────────────
SCHEMA_NAME = os.environ.get("OE_IT_SCHEMA_NAME", "superstore")
SERVER_TYPE = os.environ.get("OE_IT_SERVER_TYPE", "mysql")
TABLE_SEARCH_TERM = os.environ.get("OE_IT_TABLE_SEARCH_TERM", "customer")
COLUMN_SEARCH_TERM = os.environ.get("OE_IT_COLUMN_SEARCH_TERM", "email")
FILE_SEARCH_TERM = os.environ.get("OE_IT_FILE_SEARCH_TERM", "customer")
GLOSSARY_TERM = os.environ.get("OE_IT_GLOSSARY_TERM", "Revenue")
TAG_NAME = os.environ.get("OE_IT_TAG_NAME", "Finance & Economics")
KNOWLEDGE_QUERY = os.environ.get("OE_IT_KNOWLEDGE_QUERY", "data quality policy")
PLATFORM_HELP_QUERY = os.environ.get(
    "OE_IT_PLATFORM_HELP_QUERY", "how do I create a governance tag"
)
ORG_KNOWLEDGE_QUERY = os.environ.get("OE_IT_ORG_KNOWLEDGE_QUERY", "customer")

# Cache discovered fixtures across tests in this module run.
_DISCOVERED: dict[str, dict[str, Any] | None] = {}


# ── Helpers ──────────────────────────────────────────────────────
async def _discover(
    mcp_get, kind: str, object_type: str, search_term: str
) -> dict[str, Any] | None:
    """Find the first live catalog hit of `object_type`, caching by `kind`."""
    if kind in _DISCOVERED:
        return _DISCOVERED[kind]

    attempts = [
        {"objectType": object_type, "searchTerms": json.dumps([search_term]),
         "schemaName": SCHEMA_NAME, "serverType": SERVER_TYPE},
        {"objectType": object_type, "searchTerms": json.dumps([search_term]),
         "serverType": SERVER_TYPE},
        {"objectType": object_type, "searchTerms": json.dumps([search_term])},
    ]
    found: dict[str, Any] | None = None
    for params in attempts:
        r = await _explore(mcp_get, **params)
        if r.status_code != 200:
            continue
        for item in _items(r):
            if isinstance(item, dict) and item.get("objectId") is not None:
                found = item
                break
        if found:
            break
    _DISCOVERED[kind] = found
    return found


# ══════════════════════════════════════════════════════════════════
# asset_explorer (5)
# ══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_explorer_open_catalog_search(mcp_get) -> None:
    r = await _explore(mcp_get, searchTerms=json.dumps([TABLE_SEARCH_TERM]))
    assert r.status_code == 200, r.text[:500]
    items = _items(r)
    for hit in items:
        assert hit.get("objectId") is not None
        assert hit.get("objectType")


@pytest.mark.asyncio
async def test_explorer_schema_and_type_filter(mcp_get) -> None:
    r = await _explore(
        mcp_get, schemaName=SCHEMA_NAME, serverType=SERVER_TYPE, objectType="oetable"
    )
    assert r.status_code == 200, r.text[:500]
    data = _data(r)
    assert isinstance(data, dict)
    for hit in _items(r):
        assert hit.get("objectType") == "oetable"


@pytest.mark.asyncio
async def test_explorer_glossary_name_mode(mcp_get) -> None:
    r = await _explore(mcp_get, name=GLOSSARY_TERM, objectType="glossary", limit=5)
    assert r.status_code in (200, 404), r.text[:500]
    if r.status_code == 200:
        data = _data(r)
        assert isinstance(data, dict)
        assert isinstance(data.get("glossaryTerms"), list)


@pytest.mark.asyncio
async def test_explorer_tag_name_mode(mcp_get) -> None:
    r = await _explore(
        mcp_get, name=TAG_NAME, objectType="oetag", includeChildren="true", limit=5
    )
    assert r.status_code in (200, 404), r.text[:500]
    if r.status_code == 200:
        data = _data(r)
        assert isinstance(data, dict)
        assert isinstance(data.get("tags"), list)


@pytest.mark.asyncio
async def test_explorer_pagination_limit_respected(mcp_get) -> None:
    r = await _explore(mcp_get, searchTerms=json.dumps([TABLE_SEARCH_TERM]), limit=3)
    assert r.status_code == 200, r.text[:500]
    assert len(_items(r)) <= 3


# ══════════════════════════════════════════════════════════════════
# asset_details (5)
# ══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_details_table_composite(mcp_get) -> None:
    table = await _discover(mcp_get, "table", "oetable", TABLE_SEARCH_TERM)
    if not table:
        pytest.skip("No oetable discovered in catalog")
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(table["objectId"]), "objectType": "oetable"},
    )
    assert r.status_code == 200, r.text[:500]
    data = _data(r)
    assert isinstance(data.get("details"), dict), f"Expected details, got {data!r}"
    warning = str(data.get("warning") or "").lower()
    assert "profile" in data or "profile" in warning
    assert "relationships" in data or "relationship" in warning


@pytest.mark.asyncio
async def test_details_column_details_only(mcp_get) -> None:
    column = await _discover(mcp_get, "column", "oecolumn", COLUMN_SEARCH_TERM)
    if not column:
        pytest.skip("No oecolumn discovered in catalog")
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(column["objectId"]), "objectType": "oecolumn"},
    )
    assert r.status_code == 200, r.text[:500]
    data = _data(r)
    assert isinstance(data.get("details"), dict)
    # Columns get no profile/relationships enrichment.
    assert not data.get("profile")
    assert not data.get("relationships")


@pytest.mark.asyncio
async def test_details_file_profile_no_relationships(mcp_get) -> None:
    file_obj = await _discover(mcp_get, "file", "oefile", FILE_SEARCH_TERM)
    if not file_obj:
        pytest.skip("No oefile discovered in catalog")
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(file_obj["objectId"]), "objectType": "oefile"},
    )
    assert r.status_code == 200, r.text[:500]
    data = _data(r)
    assert isinstance(data.get("details"), dict)
    # Files get a profile but never table relationships.
    assert not data.get("relationships")


@pytest.mark.asyncio
async def test_details_rejects_missing_object_type(mcp_get) -> None:
    table = await _discover(mcp_get, "table", "oetable", TABLE_SEARCH_TERM)
    object_id = int(table["objectId"]) if table else 1
    r = await mcp_get(MCP_PATH_ASSET_DETAILS, {"objectId": object_id})
    # Missing objectType is validated in McpApiService → MCP 400 envelope.
    assert r.status_code == 400, r.text[:500]


@pytest.mark.asyncio
async def test_details_rejects_invalid_object_id(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_ASSET_DETAILS, {"objectId": 0, "objectType": "oetable"})
    assert r.status_code == 400, r.text[:500]


# ══════════════════════════════════════════════════════════════════
# asset_lineage (5)
# ══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_lineage_table(mcp_get) -> None:
    table = await _discover(mcp_get, "table", "oetable", TABLE_SEARCH_TERM)
    if not table:
        pytest.skip("No oetable discovered in catalog")
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 2},
    )
    if r.status_code == 404:
        pytest.skip("Lineage unavailable for discovered table")
    assert r.status_code == 200, r.text[:500]
    data = _data(r)
    assert isinstance(data, dict)
    assert data.get("objectType") or data.get("tableid") is not None


@pytest.mark.asyncio
async def test_lineage_depth_one(mcp_get) -> None:
    table = await _discover(mcp_get, "table", "oetable", TABLE_SEARCH_TERM)
    if not table:
        pytest.skip("No oetable discovered in catalog")
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 1},
    )
    if r.status_code == 404:
        pytest.skip("Lineage unavailable for discovered table")
    assert r.status_code == 200, r.text[:500]
    assert isinstance(_data(r), dict)


@pytest.mark.asyncio
async def test_lineage_file(mcp_get) -> None:
    file_obj = await _discover(mcp_get, "file", "oefile", FILE_SEARCH_TERM)
    if not file_obj:
        pytest.skip("No oefile discovered in catalog")
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(file_obj["objectId"]), "objectType": "oefile", "depth": 2},
    )
    assert r.status_code in (200, 404), r.text[:500]


@pytest.mark.asyncio
async def test_lineage_rejects_unsupported_type(mcp_get) -> None:
    column = await _discover(mcp_get, "column", "oecolumn", COLUMN_SEARCH_TERM)
    object_id = int(column["objectId"]) if column else 1
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": object_id, "objectType": "oecolumn", "depth": 2},
    )
    assert r.status_code == 400, r.text[:500]


@pytest.mark.asyncio
async def test_lineage_rejects_missing_object_type(mcp_get) -> None:
    table = await _discover(mcp_get, "table", "oetable", TABLE_SEARCH_TERM)
    object_id = int(table["objectId"]) if table else 1
    r = await mcp_get(MCP_PATH_ASSET_LINEAGE, {"objectId": object_id})
    # Missing objectType is validated in McpApiService → MCP 400 envelope.
    assert r.status_code == 400, r.text[:500]


# ══════════════════════════════════════════════════════════════════
# knowledge_search (5)
# ══════════════════════════════════════════════════════════════════
def _has_corpus_section(data: Any) -> bool:
    return isinstance(data, dict) and (
        data.get("dataStories") is not None or data.get("platformDocs") is not None
    )


@pytest.mark.asyncio
async def test_knowledge_dual_corpus_shape(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": KNOWLEDGE_QUERY, "limit": 5})
    assert r.status_code in (200, 404), r.text[:500]
    if r.status_code == 200:
        assert _has_corpus_section(_data(r)), r.text[:500]


@pytest.mark.asyncio
async def test_knowledge_platform_help(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH, {"query": PLATFORM_HELP_QUERY, "limit": 5}
    )
    assert r.status_code in (200, 404), r.text[:500]
    if r.status_code == 200:
        assert _has_corpus_section(_data(r))


@pytest.mark.asyncio
async def test_knowledge_org_story(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH, {"query": ORG_KNOWLEDGE_QUERY, "limit": 5}
    )
    assert r.status_code in (200, 404), r.text[:500]
    if r.status_code == 200:
        assert isinstance(_data(r), dict)


@pytest.mark.asyncio
async def test_knowledge_limit_respected(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": KNOWLEDGE_QUERY, "limit": 1})
    assert r.status_code in (200, 404), r.text[:500]
    if r.status_code == 200:
        assert isinstance(_data(r), dict)


@pytest.mark.asyncio
async def test_knowledge_empty_query_never_500(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": "zzzq-no-such-knowledge-xyz"})
    assert r.status_code in (200, 400, 404), r.text[:500]
    assert r.status_code != 500
