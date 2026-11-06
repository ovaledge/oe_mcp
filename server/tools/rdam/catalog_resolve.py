"""Resolve DAM identifiers via asset_explorer, then pass them to the DAM API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server.client import OvalEdgeError
from server.constants import (
    MCP_MEMBERSHIP_QUERY_DIRECTIONS,
    MCP_PATH_ASSET_DETAILS,
    MCP_PATH_ASSET_EXPLORER,
)
from server.tools.common import drop_none
from server.tools.rdam.helpers import (
    CATALOG_TO_RDAM_OBJECT_TYPE,
    RDAM_TO_CATALOG_OBJECT_TYPE,
    normalize_rdam_object_type,
    normalize_string_list,
    resolve_single_object_type,
)

_CATALOG_OBJECT_TYPES = frozenset(CATALOG_TO_RDAM_OBJECT_TYPE)


@dataclass(frozen=True)
class CatalogResolvedScope:
    """Identifiers to forward to the DAM access_explorer API."""

    object_path: str | list[str] | None
    object_type: str | None
    connection_id: int | None
    object_id: int | None = None
    fully_qualified_name: str | None = None
    object_name: str | None = None


def catalog_object_type_for_explorer(object_type: str | None) -> str | None:
    if object_type is None:
        return None
    raw = object_type.strip().lower()
    if raw in _CATALOG_OBJECT_TYPES:
        return raw
    rdam = normalize_rdam_object_type(raw)
    return RDAM_TO_CATALOG_OBJECT_TYPE.get(rdam) if rdam else None


def rdam_object_type_from_catalog(object_type: str | None) -> str | None:
    if object_type is None:
        return None
    raw = object_type.strip().lower()
    if raw in CATALOG_TO_RDAM_OBJECT_TYPE:
        return CATALOG_TO_RDAM_OBJECT_TYPE[raw]
    return normalize_rdam_object_type(raw)


def should_resolve_via_asset_explorer(
    query_direction: str,
    object_id: int | None,
    object_type: str | list[str] | None,
    object_path: str | list[str] | None,
    object_name: str | list[str] | None,
    fully_qualified_name: str | None,
) -> bool:
    """Look up identifiers via asset_explorer unless object_id and object_type are known.

    DAM API only. Browse and membership directions skip catalog resolve.
    """
    qd = query_direction.strip().lower()
    if qd == "browse" or qd in MCP_MEMBERSHIP_QUERY_DIRECTIONS:
        return False
    has_type = bool(resolve_single_object_type(object_type))
    if object_id is not None and object_id > 0 and has_type:
        return False
    has_name = bool(normalize_string_list(object_name))
    has_fqn = bool(fully_qualified_name and str(fully_qualified_name).strip())
    has_path = bool(normalize_string_list(object_path))
    return has_name or has_fqn or has_path


def _explorer_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _int_field(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _str_field(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _details_map(body: dict[str, Any]) -> dict[str, Any]:
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return {}
    details = data.get("details")
    if isinstance(details, dict):
        return details
    return data


def _connection_id_from_hit(
    hit: dict[str, Any], details: dict[str, Any] | None = None
) -> int | None:
    src = details or {}
    return _int_field(src.get("connectionInfoId") or src.get("connectionId")) or _int_field(
        hit.get("connectionInfoId") or hit.get("connectionId")
    )


def _hit_matches_connection_id(
    hit: dict[str, Any],
    *,
    details: dict[str, Any] | None,
    connection_id: int | None,
) -> bool:
    if connection_id is None or connection_id <= 0:
        return True
    hit_conn = _connection_id_from_hit(hit, details)
    # Unknown connection on the hit is not a mismatch; reject only a known other connector.
    return hit_conn is None or hit_conn == connection_id


async def _filter_hits_for_connection(
    client: Any,
    items: list[dict[str, Any]],
    *,
    catalog_type: str | None,
    connection_id: int | None,
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    if connection_id is None or connection_id <= 0:
        return [(hit, None) for hit in items]
    matched: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for hit in items:
        listed_conn = _connection_id_from_hit(hit, None)
        if listed_conn is not None and listed_conn != connection_id:
            continue
        if listed_conn == connection_id:
            matched.append((hit, None))
            continue
        hit_id = _int_field(hit.get("objectId"))
        hit_type = _str_field(hit.get("objectType"), catalog_type)
        details = await _load_details(client, hit_id, hit_type)
        if _hit_matches_connection_id(hit, details=details, connection_id=connection_id):
            matched.append((hit, details))
    return matched


def _scope_from_hit(
    hit: dict[str, Any],
    *,
    details: dict[str, Any] | None,
    catalog_type: str | None,
    fqn: str | None,
    name: str | None,
    connection_id: int | None,
    object_type: str | None,
) -> CatalogResolvedScope:
    src = details or {}
    hit_id = _int_field(src.get("objectId") or hit.get("objectId"))
    hit_type = _str_field(src.get("objectType"), hit.get("objectType"), catalog_type)
    path = _str_field(
        src.get("fullyQualifiedName"),
        hit.get("fullyQualifiedName"),
        fqn,
        src.get("objectName"),
        hit.get("objectName"),
        name,
    )
    conn = _connection_id_from_hit(hit, details)
    if conn is None and connection_id is not None and connection_id > 0:
        conn = connection_id
    resolved_name = _str_field(src.get("objectName"), hit.get("objectName"), name)
    rdam_type = rdam_object_type_from_catalog(hit_type) or normalize_rdam_object_type(object_type)
    return CatalogResolvedScope(
        object_path=path,
        object_type=rdam_type,
        connection_id=conn,
        object_id=hit_id,
        fully_qualified_name=path,
        object_name=resolved_name,
    )


async def _load_details(
    client: Any, hit_id: int | None, hit_type: str | None
) -> dict[str, Any] | None:
    if hit_id is None or not hit_type:
        return None
    try:
        details_body = await client.get(
            MCP_PATH_ASSET_DETAILS,
            params={"objectId": hit_id, "objectType": hit_type},
        )
    except OvalEdgeError:
        return None
    if isinstance(details_body, dict) and details_body.get("ok") is not False:
        return _details_map(details_body)
    return None


async def resolve_rdam_scope_via_asset_explorer(
    client: Any,
    *,
    source_system: str,
    object_id: int | None,
    object_type: str | None,
    object_name: str | list[str] | None,
    fully_qualified_name: str | None,
    resolve_all_matches: bool,
    connection_id: int | None,
    object_path: str | list[str] | None = None,
) -> CatalogResolvedScope | None:
    """Return DAM identifiers from asset_explorer, or None so DAM still runs with originals."""
    catalog_type = catalog_object_type_for_explorer(object_type)
    names = normalize_string_list(object_name)
    name = names[0] if names else None
    fqn = fully_qualified_name.strip() if fully_qualified_name else None
    paths = normalize_string_list(object_path)
    search_term = fqn or (paths[0] if paths else None)
    use_name = object_id is None and search_term is None and name is not None
    search = drop_none(
        searchTerms=[search_term] if search_term and object_id is None else None,
        page=1,
        limit=25,
    )
    server = source_system.strip().lower() if source_system and source_system.strip() else None
    filters = drop_none(serverType=server)
    body = drop_none(
        objectId=object_id if object_id is not None and object_id > 0 else None,
        objectType=catalog_type,
        name=name if use_name else None,
        search=search or None,
        filters=filters or None,
    )
    try:
        explorer = await client.post(MCP_PATH_ASSET_EXPLORER, body=body)
    except OvalEdgeError:
        return None
    if not isinstance(explorer, dict) or explorer.get("ok") is False or explorer.get("error"):
        return None

    items = _explorer_items(explorer)
    if not items:
        return None

    filtered_hits = await _filter_hits_for_connection(
        client,
        items,
        catalog_type=catalog_type,
        connection_id=connection_id,
    )
    if not filtered_hits:
        return None

    if resolve_all_matches and len(filtered_hits) > 1:
        scopes: list[CatalogResolvedScope] = []
        for hit, cached_details in filtered_hits:
            hit_id = _int_field(hit.get("objectId"))
            hit_type = _str_field(hit.get("objectType"), catalog_type)
            details = cached_details
            if details is None:
                details = await _load_details(client, hit_id, hit_type)
            scopes.append(
                _scope_from_hit(
                    hit,
                    details=details,
                    catalog_type=catalog_type,
                    fqn=fqn,
                    name=name,
                    connection_id=connection_id,
                    object_type=object_type,
                )
            )
        paths_out = [s.object_path for s in scopes if isinstance(s.object_path, str)]
        fqns = [s.fully_qualified_name for s in scopes if s.fully_qualified_name]
        connection_ids = {
            s.connection_id
            for s in scopes
            if isinstance(s.connection_id, int) and s.connection_id > 0
        }
        merged_connection_id = connection_ids.pop() if len(connection_ids) == 1 else None
        first = scopes[0]
        return CatalogResolvedScope(
            object_path=paths_out or first.object_path,
            object_type=first.object_type,
            connection_id=merged_connection_id,
            object_id=first.object_id if len(scopes) == 1 else None,
            fully_qualified_name=fqns[0] if len(fqns) == 1 else None,
            object_name=first.object_name if len(scopes) == 1 else None,
        )

    if len(filtered_hits) != 1:
        return None

    hit, cached_details = filtered_hits[0]
    hit_id = _int_field(hit.get("objectId"))
    hit_type = _str_field(hit.get("objectType"), catalog_type)
    details = cached_details
    if details is None:
        details = await _load_details(client, hit_id, hit_type)
    return _scope_from_hit(
        hit,
        details=details,
        catalog_type=catalog_type,
        fqn=fqn,
        name=name,
        connection_id=connection_id,
        object_type=object_type,
    )
