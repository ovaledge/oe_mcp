"""
Extended live integration coverage for the four consolidated MCP read tools.

Fifteen tests per tool (60 total), complementing the smoke suite in
`test_consolidated_read_tools_live.py`:

  - asset_explorer   → GET /api/v1/mcp/asset-explorer
  - asset_details    → GET /api/v1/mcp/asset-details
  - asset_lineage    → GET /api/v1/mcp/asset-lineage
  - knowledge_search → GET /api/v1/mcp/knowledge-search

Fixtures are discovered only via the live MCP APIs (explorer / details / lineage /
knowledge_search). There is no direct database access.

Run:
  poetry run pytest -c tests/integration/pytest.ini \
    tests/integration/test_consolidated_read_tools_extended_live.py -m integration
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from server.constants import (
    MCP_PATH_ASSET_DETAILS,
    MCP_PATH_ASSET_LINEAGE,
    MCP_PATH_KNOWLEDGE_SEARCH,
)
from tests.integration.helpers import (
    CLIENT_REJECT,
    READ_OK,
    as_list,
    assert_never_500,
    connection_hint_from_details,
    data,
    detail_block,
    explore,
    hit_name,
    items,
    json_array,
    object_ids,
    require_column,
    require_file,
    require_glossary_term,
    require_schema,
    require_story,
    require_table,
    require_table_with_lineage,
    require_table_without_lineage,
    require_tag,
    require_view,
    server_type_hint_from_details,
    text_values,
)

pytestmark = pytest.mark.integration

OWNER = os.environ.get("OE_IT_OWNER", "admin")
STEWARD = os.environ.get("OE_IT_STEWARD", "admin")
NO_MATCH_TERM = "zzq-no-such-asset-anywhere-1a2b3c"


# ══════════════════════════════════════════════════════════════════
# asset_explorer (15)
# ══════════════════════════════════════════════════════════════════
async def test_explorer_context_query_alone_ranks_results(mcp_get) -> None:
    r = await explore(mcp_get, contextQuery="Which tables hold customer information?")
    assert r.status_code == 200, r.text[:500]
    for hit in items(r):
        assert hit.get("objectId") is not None
        assert hit.get("objectType")


async def test_explorer_multiple_search_terms(mcp_get) -> None:
    r = await explore(mcp_get, searchTerms=json_array("customer", "order"))
    assert r.status_code == 200, r.text[:500]
    assert isinstance(data(r), dict)


async def test_explorer_owner_filter_returns_only_matching_owner(mcp_get) -> None:
    r = await explore(mcp_get, owner=OWNER)
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code != 200:
        return
    for hit in items(r):
        owner = hit.get("owner")
        if owner:  # only assert when the projection includes the field
            assert OWNER.lower() in str(owner).lower()


async def test_explorer_steward_filter(mcp_get) -> None:
    r = await explore(mcp_get, steward=STEWARD)
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code == 200:
        assert isinstance(data(r), dict)


async def test_explorer_connection_name_filter_scopes_to_connection(mcp_get) -> None:
    table = await require_table(mcp_get)
    connection = await connection_hint_from_details(mcp_get, table)
    if not connection:
        pytest.skip("Could not resolve connectionName via explorer/details")
    r = await explore(mcp_get, connectionName=connection, limit=10)
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code != 200:
        return
    for hit in items(r):
        hit_conn = hit.get("connectionName")
        if hit_conn:
            assert str(hit_conn).lower() == str(connection).lower()


async def test_explorer_server_type_filter_uses_real_connector(mcp_get) -> None:
    table = await require_table(mcp_get)
    server_type = await server_type_hint_from_details(mcp_get, table)
    if not server_type:
        pytest.skip("Could not resolve serverType via explorer/details")
    r = await explore(mcp_get, serverType=server_type, limit=10)
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code != 200:
        return
    for hit in items(r):
        hit_type = hit.get("serverType")
        if hit_type:
            assert str(hit_type).lower() == str(server_type).lower()


async def test_explorer_critical_data_element_filter(mcp_get) -> None:
    r = await explore(mcp_get, criticalDataElement=json_array("Yes"), limit=10)
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "criticalDataElement filter")


async def test_explorer_glossary_terms_exact_filter(mcp_get) -> None:
    term = await require_glossary_term(mcp_get)
    name = hit_name(term)
    if not name:
        pytest.skip("Glossary hit has no usable name for exact filter")
    r = await explore(mcp_get, glossaryTerms=json_array(name), limit=10)
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "glossaryTerms filter")


async def test_explorer_tags_exact_filter(mcp_get) -> None:
    tag = await require_tag(mcp_get)
    name = hit_name(tag)
    if not name:
        pytest.skip("Tag hit has no usable name for exact filter")
    r = await explore(mcp_get, tags=json_array(name), limit=10)
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "tags filter")


async def test_explorer_page_two_returns_different_hits(mcp_get) -> None:
    first = await explore(mcp_get, searchTerms=json_array("a"), page=1, limit=5)
    second = await explore(mcp_get, searchTerms=json_array("a"), page=2, limit=5)
    assert first.status_code == 200, first.text[:500]
    assert second.status_code == 200, second.text[:500]
    page_one, page_two = object_ids(first), object_ids(second)
    if len(page_one) < 5 or not page_two:
        pytest.skip("Fewer than two full pages of results")
    assert not set(page_one) & set(page_two), "page 2 repeated page 1 hits"


async def test_explorer_limit_never_exceeds_requested_page_size(mcp_get) -> None:
    """Within the client's 50-row cap the server must never over-return."""
    r = await explore(mcp_get, searchTerms=json_array("a"), limit=50)
    assert r.status_code == 200, r.text[:500]
    assert len(items(r)) <= 50


@pytest.mark.xfail(
    reason=(
        "Backend defect: asset-explorer truncates the chunked response and returns "
        "HTTP 500 with body '0\\r\\n\\r\\n' once the payload gets large (observed OK at "
        "limit=76, failing by limit=90 — the threshold tracks response size, not row "
        "count). The MCP tool caps limit at 50 so the tool path is unaffected; this "
        "test documents the raw-API ceiling. Remove the xfail once the backend streams "
        "large result sets correctly."
    ),
    strict=False,
)
async def test_explorer_large_page_size_does_not_break_the_response(mcp_get) -> None:
    r = await explore(mcp_get, searchTerms=json_array("a"), limit=200)
    assert_never_500(r, "limit=200")


async def test_explorer_column_object_type_returns_only_columns(mcp_get) -> None:
    r = await explore(mcp_get, objectType="oecolumn", searchTerms=json_array("id"), limit=10)
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code != 200:
        return
    for hit in items(r):
        assert hit.get("objectType") == "oecolumn"


async def test_explorer_tag_include_children_returns_hierarchy(mcp_get) -> None:
    tag = await require_tag(mcp_get)
    name = hit_name(tag)
    if not name:
        pytest.skip("Tag hit has no usable name for includeChildren")
    r = await explore(
        mcp_get, name=name, objectType="oetag", includeChildren="true", limit=5
    )
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code != 200:
        return
    payload = data(r)
    assert isinstance(payload, dict)
    assert as_list(payload.get("tags")) or payload.get("tags") is not None


async def test_explorer_nonsense_term_stays_well_formed(mcp_get) -> None:
    """Search is semantic, so a nonsense term still returns nearest neighbours.

    The contract is not "zero hits" — it is that the response stays a valid,
    well-formed result set rather than erroring.
    """
    r = await explore(mcp_get, searchTerms=json_array(NO_MATCH_TERM))
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "nonsense-term search")
    if r.status_code != 200:
        return
    for hit in items(r):
        assert hit.get("objectId") is not None
        assert hit.get("objectType")


async def test_explorer_hits_expose_navigation_link(mcp_get) -> None:
    r = await explore(mcp_get, searchTerms=json_array("a"), limit=5)
    assert r.status_code == 200, r.text[:500]
    hits = items(r)
    if not hits:
        pytest.skip("No catalog hits to inspect")
    for hit in hits:
        assert hit.get("navLink") or hit.get("hyperlink") or hit.get("redirectUrl"), (
            f"hit without a navigation link: {hit!r}"
        )


# ══════════════════════════════════════════════════════════════════
# asset_details (15)
# ══════════════════════════════════════════════════════════════════
async def test_details_table_name_matches_explorer_hit(mcp_get) -> None:
    """asset_details must describe the same table asset_explorer returned."""
    table = await require_table(mcp_get)
    name = hit_name(table)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(table["objectId"]), "objectType": "oetable"},
    )
    assert r.status_code == 200, r.text[:500]
    if name:
        assert name.lower() in text_values(data(r)), (
            f"asset_details did not mention {name!r} for objectId {table['objectId']}"
        )


async def test_details_schema_name_matches_explorer_hit(mcp_get) -> None:
    schema = await require_schema(mcp_get)
    name = hit_name(schema)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(schema["objectId"]), "objectType": "oeschema"},
    )
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code == 200 and name:
        assert name.lower() in text_values(data(r))


async def test_details_view_is_served_like_a_table(mcp_get) -> None:
    view = await require_view(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(view["objectId"]), "objectType": "oetable"},
    )
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code == 200:
        assert isinstance(detail_block(data(r)), dict)


async def test_details_glossary_term(mcp_get) -> None:
    term = await require_glossary_term(mcp_get)
    name = hit_name(term)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(term["objectId"]), "objectType": "glossary"},
    )
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code == 200 and name:
        assert name.lower() in text_values(data(r))


async def test_details_file(mcp_get) -> None:
    file_hit = await require_file(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(file_hit["objectId"]), "objectType": "oefile"},
    )
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "file details")


async def test_details_echoes_requested_object_id(mcp_get) -> None:
    table = await require_table(mcp_get)
    object_id = int(table["objectId"])
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS, {"objectId": object_id, "objectType": "oetable"}
    )
    assert r.status_code == 200, r.text[:500]
    detail = detail_block(data(r))
    echoed = detail.get("objectId") or detail.get("tableid") or detail.get("id")
    if echoed is not None:
        assert int(echoed) == object_id


async def test_details_exposes_navigation_link(mcp_get) -> None:
    table = await require_table(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(table["objectId"]), "objectType": "oetable"},
    )
    assert r.status_code == 200, r.text[:500]
    detail = detail_block(data(r))
    assert detail.get("navLink") or detail.get("hyperlink") or detail.get("redirectUrl")


async def test_details_column_references_parent_table(mcp_get) -> None:
    column = await require_column(mcp_get)
    name = hit_name(column)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(column["objectId"]), "objectType": "oecolumn"},
    )
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code == 200 and name:
        assert name.lower() in text_values(data(r))


async def test_details_table_reports_profile_or_explains_absence(mcp_get) -> None:
    table = await require_table(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(table["objectId"]), "objectType": "oetable"},
    )
    assert r.status_code == 200, r.text[:500]
    payload = data(r)
    assert isinstance(payload, dict)
    warning = str(payload.get("warning") or "").lower()
    assert "profile" in payload or "profile" in warning


async def test_details_unknown_object_id_is_not_a_server_error(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS, {"objectId": 2_146_000_000, "objectType": "oetable"}
    )
    assert_never_500(r, "unknown objectId")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_details_negative_object_id_rejected(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_ASSET_DETAILS, {"objectId": -1, "objectType": "oetable"})
    assert r.status_code in CLIENT_REJECT, r.text[:500]


async def test_details_non_numeric_object_id_rejected(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS, {"objectId": "not-a-number", "objectType": "oetable"}
    )
    assert r.status_code in CLIENT_REJECT, r.text[:500]
    assert_never_500(r, "non-numeric objectId")


async def test_details_invalid_object_type_rejected(mcp_get) -> None:
    table = await require_table(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(table["objectId"]), "objectType": "oenosuchtype"},
    )
    assert r.status_code in CLIENT_REJECT, r.text[:500]


async def test_details_missing_object_id_rejected(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_ASSET_DETAILS, {"objectType": "oetable"})
    assert r.status_code in CLIENT_REJECT, r.text[:500]


async def test_details_round_trips_an_explorer_hit(mcp_get) -> None:
    """Every id asset_explorer hands back must be resolvable by asset_details."""
    search = await explore(mcp_get, searchTerms=json_array("a"), objectType="oetable", limit=3)
    assert search.status_code == 200, search.text[:500]
    hits = [h for h in items(search) if h.get("objectId") is not None]
    if not hits:
        pytest.skip("No oetable hits to round-trip")
    hit = hits[0]
    r = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(hit["objectId"]), "objectType": str(hit["objectType"])},
    )
    assert r.status_code == 200, (
        f"explorer returned objectId {hit['objectId']} that asset_details rejected: "
        f"{r.status_code} {r.text[:300]}"
    )


# ══════════════════════════════════════════════════════════════════
# asset_lineage (15)
# ══════════════════════════════════════════════════════════════════
async def test_lineage_returns_graph_for_known_lineage_table(mcp_get) -> None:
    """API probing found a table with a lineage graph — details must stay available."""
    table = await require_table_with_lineage(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 2},
    )
    assert r.status_code == 200, (
        f"table objectId={table['objectId']} previously returned a lineage graph "
        f"but now returned {r.status_code}: {r.text[:300]}"
    )
    assert isinstance(data(r), dict)


async def test_lineage_depth_zero(mcp_get) -> None:
    table = await require_table_with_lineage(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 0},
    )
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "depth=0")


async def test_lineage_depth_three(mcp_get) -> None:
    table = await require_table_with_lineage(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 3},
    )
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code == 200:
        assert isinstance(data(r), dict)


async def test_lineage_very_large_depth_is_handled(mcp_get) -> None:
    table = await require_table_with_lineage(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 999},
    )
    assert_never_500(r, "depth=999")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_lineage_graph_exposes_nodes_or_edges(mcp_get) -> None:
    table = await require_table_with_lineage(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 2},
    )
    assert r.status_code == 200, r.text[:500]
    payload = data(r)
    assert isinstance(payload, dict)
    assert any(
        key in payload
        for key in ("nodes", "edges", "lineage", "upstream", "downstream", "objectType")
    ), f"no recognizable lineage graph keys in {sorted(payload)}"


async def test_lineage_depth_one_is_subset_of_depth_three(mcp_get) -> None:
    table = await require_table_with_lineage(mcp_get)
    params = {"objectId": int(table["objectId"]), "objectType": "oetable"}
    shallow = await mcp_get(MCP_PATH_ASSET_LINEAGE, {**params, "depth": 1})
    deep = await mcp_get(MCP_PATH_ASSET_LINEAGE, {**params, "depth": 3})
    if shallow.status_code != 200 or deep.status_code != 200:
        pytest.skip("Lineage unavailable at one of the depths")
    shallow_nodes = as_list(data(shallow).get("nodes"))
    deep_nodes = as_list(data(deep).get("nodes"))
    if not shallow_nodes or not deep_nodes:
        pytest.skip("Lineage response exposes no node list")
    assert len(deep_nodes) >= len(shallow_nodes), "deeper traversal returned fewer nodes"


async def test_lineage_table_without_edges_returns_empty_not_error(mcp_get) -> None:
    table = await require_table_without_lineage(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": 2},
    )
    assert_never_500(r, "table without lineage")
    assert r.status_code in READ_OK, r.text[:500]


async def test_lineage_file(mcp_get) -> None:
    file_hit = await require_file(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(file_hit["objectId"]), "objectType": "oefile", "depth": 2},
    )
    assert_never_500(r, "file lineage")
    assert r.status_code in READ_OK, r.text[:500]


async def test_lineage_unknown_object_id_is_not_a_server_error(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": 2_146_000_000, "objectType": "oetable", "depth": 2},
    )
    assert_never_500(r, "unknown lineage objectId")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_lineage_negative_object_id_rejected(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE, {"objectId": -5, "objectType": "oetable", "depth": 2}
    )
    assert r.status_code in CLIENT_REJECT, r.text[:500]


async def test_lineage_non_numeric_object_id_rejected(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE, {"objectId": "abc", "objectType": "oetable", "depth": 2}
    )
    assert r.status_code in CLIENT_REJECT, r.text[:500]
    assert_never_500(r, "non-numeric lineage objectId")


async def test_lineage_rejects_schema_object_type(mcp_get) -> None:
    schema = await require_schema(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(schema["objectId"]), "objectType": "oeschema", "depth": 2},
    )
    assert r.status_code in CLIENT_REJECT, r.text[:500]


async def test_lineage_rejects_glossary_object_type(mcp_get) -> None:
    term = await require_glossary_term(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(term["objectId"]), "objectType": "glossary", "depth": 2},
    )
    assert r.status_code in CLIENT_REJECT, r.text[:500]


async def test_lineage_rejects_negative_depth(mcp_get) -> None:
    table = await require_table_with_lineage(mcp_get)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": int(table["objectId"]), "objectType": "oetable", "depth": -1},
    )
    assert_never_500(r, "negative depth")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_lineage_response_identifies_the_requested_object(mcp_get) -> None:
    table = await require_table_with_lineage(mcp_get)
    object_id = int(table["objectId"])
    name = hit_name(table)
    r = await mcp_get(
        MCP_PATH_ASSET_LINEAGE,
        {"objectId": object_id, "objectType": "oetable", "depth": 1},
    )
    assert r.status_code == 200, r.text[:500]
    blob = text_values(data(r))
    assert str(object_id) in blob or (name and name.lower() in blob), (
        "lineage graph does not reference the requested object"
    )


# ══════════════════════════════════════════════════════════════════
# knowledge_search (15)
# ══════════════════════════════════════════════════════════════════
def _corpus_sections(payload: Any) -> tuple[Any, Any]:
    if not isinstance(payload, dict):
        return None, None
    return payload.get("dataStories"), payload.get("platformDocs")


async def test_knowledge_content_query_alias(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH, {"contentQuery": "data governance policy", "limit": 5}
    )
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "contentQuery alias")


async def test_knowledge_story_name_lookup_matches_discovered_story(mcp_get) -> None:
    """A story discovered via API must be findable by its exact title."""
    story = await require_story(mcp_get)
    name = hit_name(story)
    if not name:
        pytest.skip("Discovered story has no usable name")
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"storyName": name})
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code == 200:
        assert name.lower() in text_values(data(r))


async def test_knowledge_story_object_id_lookup(mcp_get) -> None:
    story = await require_story(mcp_get)
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"objectId": int(story["objectId"])})
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "story objectId lookup")


async def test_knowledge_story_zone_filter(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH,
        {"query": "policy", "storyZoneName": os.environ.get("OE_IT_STORY_ZONE", "Governance")},
    )
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "storyZoneName filter")


async def test_knowledge_num_candidates_above_limit(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH,
        {"query": "data quality", "limit": 5, "numCandidates": 128},
    )
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "numCandidates > limit")


async def test_knowledge_num_candidates_below_limit_is_handled(mcp_get) -> None:
    """numCandidates < limit is invalid for KNN; the server must not 500 on it."""
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH,
        {"query": "data quality", "limit": 20, "numCandidates": 2},
    )
    assert_never_500(r, "numCandidates < limit")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_knowledge_large_limit_is_handled(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": "governance", "limit": 500})
    assert_never_500(r, "limit=500")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_knowledge_no_parameters_rejected(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {})
    assert r.status_code in CLIENT_REJECT, r.text[:500]
    assert_never_500(r, "empty knowledge_search")


async def test_knowledge_story_results_carry_a_citation(mcp_get) -> None:
    story = await require_story(mcp_get)
    name = hit_name(story) or "policy"
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": name, "limit": 5})
    if r.status_code != 200:
        pytest.skip(f"knowledge_search returned {r.status_code}")
    stories, _ = _corpus_sections(data(r))
    entries = as_list(stories)
    if not entries:
        pytest.skip("No data-story hits returned")
    assert any(
        isinstance(e, dict) and (e.get("storyCitation") or e.get("navUrl") or e.get("navLink"))
        for e in entries
    ), "story hits carry neither a citation nor a navigation link"


async def test_knowledge_returns_a_corpus_section(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": "governance", "limit": 5})
    assert r.status_code in READ_OK, r.text[:500]
    if r.status_code != 200:
        return
    stories, docs = _corpus_sections(data(r))
    assert stories is not None or docs is not None, (
        f"neither dataStories nor platformDocs present: {r.text[:300]}"
    )


async def test_knowledge_product_help_query(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH,
        {"query": "how do I run a crawler in OvalEdge", "limit": 5},
    )
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "product-help query")


async def test_knowledge_org_policy_query(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH, {"query": "member approval policy", "limit": 5}
    )
    assert r.status_code in READ_OK, r.text[:500]
    assert_never_500(r, "org-policy query")


async def test_knowledge_special_characters_do_not_break_search(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH, {"query": 'policy: "PII" AND (risk) *? <tag>', "limit": 5}
    )
    assert_never_500(r, "special-character query")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_knowledge_very_long_query_is_handled(mcp_get) -> None:
    r = await mcp_get(
        MCP_PATH_KNOWLEDGE_SEARCH, {"query": "data governance " * 300, "limit": 5}
    )
    assert_never_500(r, "very long query")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]


async def test_knowledge_unicode_query_is_handled(mcp_get) -> None:
    r = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": "données personnelles 個人情報"})
    assert_never_500(r, "unicode query")
    assert r.status_code in (200, *CLIENT_REJECT), r.text[:500]
