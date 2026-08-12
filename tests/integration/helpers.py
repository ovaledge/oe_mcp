"""Shared response helpers for the live MCP read-tool integration tests."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from server.constants import (
    MCP_PATH_ASSET_DETAILS,
    MCP_PATH_ASSET_EXPLORER,
    MCP_PATH_ASSET_LINEAGE,
    MCP_PATH_KNOWLEDGE_SEARCH,
)

# A live catalog may legitimately answer "nothing there" as 404 rather than an
# empty 200, so reads accept both. 500 is never acceptable and is asserted against
# explicitly by the resilience tests.
READ_OK = (200, 404)
CLIENT_REJECT = (400, 404, 422)


def body(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    assert isinstance(payload, dict), f"Expected JSON object, got {payload!r}"
    assert payload.get("ok") is not False, f"API ok=false: {payload}"
    return payload


def data(response: httpx.Response) -> Any:
    return body(response).get("data")


def items(response: httpx.Response) -> list[dict[str, Any]]:
    payload = data(response)
    hits = payload.get("items") if isinstance(payload, dict) else None
    return hits if isinstance(hits, list) else []


def object_ids(response: httpx.Response) -> list[int]:
    return [
        int(hit["objectId"])
        for hit in items(response)
        if isinstance(hit, dict) and hit.get("objectId") is not None
    ]


def as_list(value: Any) -> list[Any]:
    """Normalize an API section that may be a list, a wrapper dict, or absent."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "content", "results", "data"):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
    return []


def json_array(*values: str) -> str:
    """Encode a keyword list the way the asset-explorer wire format expects."""
    return json.dumps(list(values), ensure_ascii=False)


async def explore(mcp_get: Any, **params: Any) -> httpx.Response:
    payload: dict[str, Any] = {"page": 1, "limit": 10}
    payload.update({k: v for k, v in params.items() if v is not None})
    return await mcp_get(MCP_PATH_ASSET_EXPLORER, payload)


def assert_never_500(response: httpx.Response, context: str) -> None:
    assert response.status_code != 500, (
        f"{context} returned a server error: {response.status_code} {response.text[:300]}"
    )


def detail_block(payload: Any) -> dict[str, Any]:
    """asset_details returns {details: {...}} or a flat metadata document."""
    if not isinstance(payload, dict):
        return {}
    details = payload.get("details")
    return details if isinstance(details, dict) else payload


def text_values(payload: Any) -> str:
    """Flatten a response to lowercase text for tolerant name matching."""
    return str(payload).lower()


def hit_name(hit: dict[str, Any]) -> str:
    return str(
        hit.get("objectName")
        or hit.get("name")
        or hit.get("title")
        or hit.get("storyName")
        or ""
    )


async def first_explorer_hit(mcp_get: Any, **params: Any) -> dict[str, Any] | None:
    """Return the first asset_explorer hit, or None when the catalog has no match."""
    response = await explore(mcp_get, **params)
    if response.status_code != 200:
        return None
    hits = [
        h for h in items(response) if isinstance(h, dict) and h.get("objectId") is not None
    ]
    return hits[0] if hits else None


async def require_explorer_hit(mcp_get: Any, what: str, **params: Any) -> dict[str, Any]:
    """Discover a live catalog object via asset_explorer or skip the test."""
    hit = await first_explorer_hit(mcp_get, **params)
    if hit is None:
        pytest.skip(f"No {what} found via asset_explorer (API-only discovery)")
    return hit


async def require_table(mcp_get: Any) -> dict[str, Any]:
    return await require_explorer_hit(
        mcp_get, "oetable", objectType="oetable", searchTerms=json_array("a"), limit=20
    )


async def require_column(mcp_get: Any) -> dict[str, Any]:
    return await require_explorer_hit(
        mcp_get, "oecolumn", objectType="oecolumn", searchTerms=json_array("id"), limit=20
    )


async def require_file(mcp_get: Any) -> dict[str, Any]:
    return await require_explorer_hit(
        mcp_get, "oefile", objectType="oefile", searchTerms=json_array("a"), limit=20
    )


async def require_schema(mcp_get: Any) -> dict[str, Any]:
    return await require_explorer_hit(
        mcp_get, "oeschema", objectType="oeschema", searchTerms=json_array("a"), limit=20
    )


async def require_glossary_term(mcp_get: Any) -> dict[str, Any]:
    return await require_explorer_hit(
        mcp_get,
        "glossary term",
        objectType="glossary",
        searchTerms=json_array("a"),
        limit=20,
    )


async def require_tag(mcp_get: Any) -> dict[str, Any]:
    return await require_explorer_hit(
        mcp_get, "oetag", objectType="oetag", searchTerms=json_array("a"), limit=20
    )


def _looks_like_view(detail: dict[str, Any], blob: str) -> bool:
    for key in ("type", "tableType", "objectSubtype", "subtype"):
        value = str(detail.get(key) or "").lower()
        if value == "view" or "view" in value:
            return True
    return "view" in blob and "tabletype" in blob.replace(" ", "")


async def require_view(mcp_get: Any) -> dict[str, Any]:
    """Probe explorer tables until asset_details indicates a VIEW."""
    search = await explore(
        mcp_get, objectType="oetable", searchTerms=json_array("a"), limit=20
    )
    if search.status_code != 200:
        pytest.skip("Could not discover tables while looking for a VIEW")
    for hit in items(search):
        if not isinstance(hit, dict) or hit.get("objectId") is None:
            continue
        response = await mcp_get(
            MCP_PATH_ASSET_DETAILS,
            {"objectId": int(hit["objectId"]), "objectType": "oetable"},
        )
        if response.status_code != 200:
            continue
        payload = data(response)
        detail = detail_block(payload)
        if _looks_like_view(detail, text_values(payload)):
            return hit
    pytest.skip("No VIEW found via asset_explorer + asset_details probing")


async def require_story(mcp_get: Any) -> dict[str, Any]:
    """Prefer explorer oestory; fall back to knowledge_search story hits."""
    hit = await first_explorer_hit(
        mcp_get, objectType="oestory", searchTerms=json_array("a"), limit=20
    )
    if hit is not None:
        return hit
    response = await mcp_get(MCP_PATH_KNOWLEDGE_SEARCH, {"query": "policy", "limit": 10})
    if response.status_code != 200:
        pytest.skip("No data story found via explorer or knowledge_search")
    payload = data(response)
    stories = payload.get("dataStories") if isinstance(payload, dict) else None
    for entry in as_list(stories):
        if not isinstance(entry, dict):
            continue
        object_id = entry.get("objectId") or entry.get("id")
        name = entry.get("storyName") or entry.get("name") or entry.get("title")
        if object_id is not None:
            return {
                "objectId": object_id,
                "objectName": name,
                "objectType": "oestory",
            }
    pytest.skip("No data story found via explorer or knowledge_search")


def lineage_has_graph(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ("nodes", "edges", "lineage", "upstream", "downstream"):
        value = payload.get(key)
        if as_list(value) or (isinstance(value, dict) and value):
            return True
    return False


async def require_table_with_lineage(mcp_get: Any) -> dict[str, Any]:
    """Probe explorer tables until asset_lineage returns a recognizable graph."""
    search = await explore(
        mcp_get, objectType="oetable", searchTerms=json_array("a"), limit=20
    )
    if search.status_code != 200:
        pytest.skip("Could not discover tables for lineage probing")
    for hit in items(search):
        if not isinstance(hit, dict) or hit.get("objectId") is None:
            continue
        lineage = await mcp_get(
            MCP_PATH_ASSET_LINEAGE,
            {"objectId": int(hit["objectId"]), "objectType": "oetable", "depth": 2},
        )
        if lineage.status_code == 200 and lineage_has_graph(data(lineage)):
            return hit
    pytest.skip("No oetable with lineage graph found via API probing")


async def require_table_without_lineage(mcp_get: Any) -> dict[str, Any]:
    """Probe explorer tables until asset_lineage returns empty/no graph."""
    search = await explore(
        mcp_get, objectType="oetable", searchTerms=json_array("a"), limit=20
    )
    if search.status_code != 200:
        pytest.skip("Could not discover tables for empty-lineage probing")
    for hit in items(search):
        if not isinstance(hit, dict) or hit.get("objectId") is None:
            continue
        lineage = await mcp_get(
            MCP_PATH_ASSET_LINEAGE,
            {"objectId": int(hit["objectId"]), "objectType": "oetable", "depth": 2},
        )
        payload = data(lineage) if lineage.status_code == 200 else None
        if lineage.status_code in READ_OK and not lineage_has_graph(payload):
            return hit
    pytest.skip("No oetable without lineage graph found via API probing")


async def connection_hint_from_details(mcp_get: Any, table_hit: dict[str, Any]) -> str | None:
    """Read connectionName from asset_details when explorer hit omits it."""
    from_hit = table_hit.get("connectionName")
    if from_hit:
        return str(from_hit)
    response = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(table_hit["objectId"]), "objectType": "oetable"},
    )
    if response.status_code != 200:
        return None
    detail = detail_block(data(response))
    info = detail.get("connectionInfo")
    if isinstance(info, dict) and info.get("name"):
        return str(info["name"])
    return str(detail["connectionName"]) if detail.get("connectionName") else None


async def server_type_hint_from_details(mcp_get: Any, table_hit: dict[str, Any]) -> str | None:
    from_hit = table_hit.get("serverType")
    if from_hit:
        return str(from_hit)
    response = await mcp_get(
        MCP_PATH_ASSET_DETAILS,
        {"objectId": int(table_hit["objectId"]), "objectType": "oetable"},
    )
    if response.status_code != 200:
        return None
    detail = detail_block(data(response))
    info = detail.get("connectionInfo")
    if isinstance(info, dict) and info.get("serverType"):
        return str(info["serverType"])
    return str(detail["serverType"]) if detail.get("serverType") else None
