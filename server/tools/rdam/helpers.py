"""
Native source-system access helpers (RDAM harvest).

Queries OvalEdge-harvested RDAM privilege metadata — not OvalEdge catalog ACLs
(see get_catalog_object_access when that ships) and not catalog data-sources.
"""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_SOURCE_SYSTEM_ACCESS,
    MCP_QUERY_DIRECTIONS,
    MCP_RDAM_OBJECT_TYPE_ALL,
    MCP_RDAM_OBJECT_TYPES,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR,
    MCP_SOURCE_SYSTEMS,
    MCP_TABLE_SCHEMA_DISCOVERY_MAX_PROBES,
)
from server.tools.common import error_payload

_RDAM_OBJECT_TYPE_ALIASES = {
    "oeschema": "schema",
    "oetable": "table",
    "oecolumn": "column",
}

_GRANT_SUMMARY_LEVELS = ("database", "schema", "table", "column", "project", "report")
_GRANT_MECHANISMS = ("direct", "group", "role")
_FULL_TABLE_PATH_SEGMENTS = 3


def _path_segments(object_path: str) -> list[str]:
    return [segment.strip() for segment in object_path.split(".") if segment.strip()]


def is_incomplete_table_object_path(object_path: str) -> bool:
    """True when object_path is not a full dbName.schema.table (3 segments)."""
    return len(_path_segments(object_path)) < _FULL_TABLE_PATH_SEGMENTS


def _schema_from_table_path(object_path: str) -> str | None:
    parts = _path_segments(object_path)
    if len(parts) >= _FULL_TABLE_PATH_SEGMENTS:
        return parts[-2]
    if len(parts) == 2:
        return parts[0]
    return None


def _schemas_from_match_candidates(candidates: list[Any]) -> list[str]:
    schemas: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        path = candidate.get("objectPath")
        if not isinstance(path, str):
            continue
        schema = _schema_from_table_path(path)
        if schema and schema not in seen:
            seen.add(schema)
            schemas.append(schema)
    return schemas


def _table_grant_paths(grants: list[Any]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for grant in grants:
        if not isinstance(grant, dict) or grant.get("objectLevel") != "table":
            continue
        path = grant.get("objectPath")
        if not isinstance(path, str) or path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _match_candidates_from_table_paths(
    table_paths: list[str],
    grants: list[Any],
) -> list[dict[str, Any]]:
    connection_id = next(
        (
            grant.get("connectionId")
            for grant in grants
            if isinstance(grant, dict) and grant.get("connectionId") is not None
        ),
        None,
    )
    return [
        {
            "objectPath": path,
            "objectLevel": "table",
            "connectionId": connection_id,
        }
        for path in table_paths
    ]


def _schema_disambiguation_advisory(object_path: str, options: list[str]) -> str:
    listed = ", ".join(options[:20])
    suffix = " …" if len(options) > 20 else ""
    return (
        f"Table {object_path!r} matches multiple schemas on this connection. "
        f"Ask the user which schema holds this table, then retry with "
        f"object_path=dbName.schema.table. Candidates: {listed}{suffix}. "
        "Do not guess a schema."
    )


def _schema_selection_advisory(object_path: str, options: list[str] | None = None) -> str:
    if options:
        return _schema_disambiguation_advisory(object_path, options)
    return (
        f"Table {object_path!r} is ambiguous without a schema. Ask the user which schema "
        f"holds this table, then retry with object_path=dbName.schema.table. "
        "Do not guess a schema."
    )


def _parse_incomplete_table_path(object_path: str) -> tuple[str | None, str | None]:
    """Return (database, table) for 1- or 2-segment incomplete table paths."""
    parts = _path_segments(object_path)
    if len(parts) == 1:
        return None, parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def _schema_names_from_schema_grants(grants: list[Any]) -> list[str]:
    schemas: list[str] = []
    seen: set[str] = set()
    for grant in grants:
        if not isinstance(grant, dict) or grant.get("objectLevel") != "schema":
            continue
        path = grant.get("objectPath")
        if not isinstance(path, str):
            continue
        parts = _path_segments(path)
        schema = parts[-1] if parts else path
        if schema and schema not in seen:
            seen.add(schema)
            schemas.append(schema)
    return schemas


def _has_table_level_grants(result: dict[str, Any]) -> bool:
    if not result.get("ok"):
        return False
    data = result.get("data")
    if not isinstance(data, dict):
        return False
    grants = data.get("grants")
    if not isinstance(grants, list):
        return False
    return any(
        isinstance(grant, dict) and grant.get("objectLevel") == "table" for grant in grants
    )


def _probe_path_for_table(database: str | None, schema: str, table: str) -> str:
    if database:
        return f"{database}.{schema}.{table}"
    return f"{schema}.{table}"


def _apply_schema_discovery_result(
    result: dict[str, Any],
    object_path: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    data = result.get("data")
    if not isinstance(data, dict):
        data = {}
    schemas = _schemas_from_match_candidates(candidates)
    options = schemas or [str(candidate.get("objectPath")) for candidate in candidates]
    return {
        "ok": True,
        "message": result.get("message") or "",
        "data": {
            **data,
            "grants": [],
            "ambiguousMatch": len(candidates) >= 2,
            "matchCandidates": candidates,
            "requiresSchemaSelection": True,
            "advisoryMessage": _schema_disambiguation_advisory(object_path, options),
            "discoveredSchemaCandidates": True,
        },
    }


async def discover_table_schema_candidates(
    client: Any,
    source_system: str,
    connection_id: int,
    object_path: str,
    grants_hint_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Probe schemas from a partial-path grants hint to find where the table exists.

    Only schemas with table-level RDAM grants are returned (schema-only parent
    matches such as customerinfo.actor are excluded).
    """
    database, table = _parse_incomplete_table_path(object_path)
    if not table:
        return []

    hint = grants_hint_result
    if hint is None or not hint.get("ok"):
        hint = await client.get(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": source_system.strip().lower(),
                "queryDirection": "object_to_users",
                "objectPath": table,
                "objectType": "table",
                "connectionId": connection_id,
            },
        )

    if not hint.get("ok"):
        return []

    hint_data = hint.get("data")
    if not isinstance(hint_data, dict):
        return []

    schema_names = _schema_names_from_schema_grants(hint_data.get("grants") or [])
    candidates: list[dict[str, Any]] = []
    for schema in schema_names[:MCP_TABLE_SCHEMA_DISCOVERY_MAX_PROBES]:
        probe_path = _probe_path_for_table(database, schema, table)
        try:
            probe = await client.get(
                MCP_PATH_SOURCE_SYSTEM_ACCESS,
                params={
                    "sourceSystem": source_system.strip().lower(),
                    "queryDirection": "object_to_users",
                    "objectPath": probe_path,
                    "objectType": "table",
                    "connectionId": connection_id,
                },
            )
        except OvalEdgeError:
            continue
        if not _has_table_level_grants(probe):
            continue
        candidates.append(
            {
                "objectPath": probe_path,
                "objectLevel": "table",
                "connectionId": connection_id,
            }
        )
    return candidates


def should_discover_table_schema_candidates(
    query_direction: str,
    object_type: str | None,
    object_path: str | list[str] | None,
    result: dict[str, Any],
    resolve_all_matches: bool,
) -> bool:
    if resolve_all_matches or object_type is None:
        return False
    if query_direction.strip().lower() != "object_to_users":
        return False
    if object_type.lower() != "table":
        return False
    paths = normalize_string_list(object_path)
    if len(paths) != 1 or not is_incomplete_table_object_path(paths[0]):
        return False
    data = result.get("data")
    if isinstance(data, dict) and data.get("matchCandidates"):
        return False
    if isinstance(data, dict) and data.get("requiresSchemaSelection"):
        return True
    if not result.get("ok"):
        return True
    return False


async def enrich_table_schema_candidates(
    client: Any,
    result: dict[str, Any],
    source_system: str,
    connection_id: int | None,
    object_path: str | list[str] | None,
    query_direction: str,
    object_type: str | None,
    resolve_all_matches: bool,
    grants_hint_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not should_discover_table_schema_candidates(
        query_direction, object_type, object_path, result, resolve_all_matches
    ):
        return result
    if connection_id is None:
        return result

    paths = normalize_string_list(object_path)
    path = paths[0]
    grants_hint = (
        grants_hint_result if grants_hint_result and grants_hint_result.get("ok") else None
    )
    candidates = await discover_table_schema_candidates(
        client,
        source_system,
        connection_id,
        path,
        grants_hint,
    )
    if not candidates:
        return result
    return _apply_schema_discovery_result(result, path, candidates)


def shape_object_to_users_disambiguation(
    result: dict[str, Any],
    object_path: str | list[str] | None,
    object_type: str | None,
) -> dict[str, Any]:
    """
    When object_to_users targets a table with an incomplete path, surface schema
    disambiguation instead of misleading parent grants or silent multi-schema merges.
    """
    if not result.get("ok") or object_type is None or object_type.lower() != "table":
        return result

    paths = normalize_string_list(object_path)
    if len(paths) != 1:
        return result
    path = paths[0]
    if not is_incomplete_table_object_path(path):
        return result

    data = result.get("data")
    if not isinstance(data, dict):
        return result

    candidates = data.get("matchCandidates")
    if not isinstance(candidates, list):
        candidates = []

    if data.get("ambiguousMatch") and len(candidates) >= 2:
        schemas = _schemas_from_match_candidates(candidates)
        options = schemas or [
            str(candidate.get("objectPath"))
            for candidate in candidates
            if isinstance(candidate, dict) and candidate.get("objectPath")
        ]
        return {
            **result,
            "data": {
                **data,
                "grants": [],
                "requiresSchemaSelection": True,
                "advisoryMessage": _schema_disambiguation_advisory(path, options),
            },
        }

    grants = data.get("grants")
    if not isinstance(grants, list):
        return result

    table_paths = _table_grant_paths(grants)
    if len(table_paths) >= 2:
        grant_schemas = [_schema_from_table_path(table_path) for table_path in table_paths]
        schema_options = [schema for schema in grant_schemas if schema]
        return {
            **result,
            "data": {
                **data,
                "grants": [],
                "ambiguousMatch": True,
                "matchCandidates": _match_candidates_from_table_paths(table_paths, grants),
                "requiresSchemaSelection": True,
                "advisoryMessage": _schema_disambiguation_advisory(
                    path,
                    schema_options or table_paths,
                ),
            },
        }

    if len(table_paths) == 1:
        return result

    if grants:
        return {
            **result,
            "data": {
                **data,
                "grants": [],
                "requiresSchemaSelection": True,
                "advisoryMessage": _schema_selection_advisory(path),
                "schemaHints": _schema_names_from_schema_grants(grants),
            },
        }

    return result


def compose_object_path_segment(scope: str, object_name: str) -> str:
    """Join db/schema scope with a bare table name."""
    segments = _path_segments(scope)
    if len(segments) >= _FULL_TABLE_PATH_SEGMENTS:
        return ".".join(segments[:2] + [object_name])
    if not segments:
        return object_name
    return f"{scope}.{object_name}"


def compose_object_path(
    object_path: str | list[str] | None,
    object_name: str | list[str] | None,
) -> str | list[str] | None:
    """Merge optional object_path scope with object_name before calling the API."""
    names = normalize_string_list(object_name)
    if not names:
        return object_path
    if len(names) > 1:
        return names
    name = names[0]
    paths = normalize_string_list(object_path)
    if not paths:
        return name
    if len(paths) == 1:
        return compose_object_path_segment(paths[0], name)
    return [compose_object_path_segment(path, name) for path in paths]


def _grant_privilege_set(grant: dict[str, Any]) -> set[str]:
    privs = grant.get("privileges")
    if isinstance(privs, str):
        return {privs.strip().upper()} if privs.strip() else set()
    if isinstance(privs, list):
        return {str(priv).strip().upper() for priv in privs if str(priv).strip()}
    return set()


def filter_grants_by_privileges(
    result: dict[str, Any],
    privileges: str | list[str] | None,
) -> dict[str, Any]:
    """Keep grants whose native privilege list intersects the requested privileges."""
    wanted = {value.upper() for value in normalize_string_list(privileges)}
    if not wanted or not result.get("ok"):
        return result
    data = result.get("data")
    if not isinstance(data, dict):
        return result
    grants = data.get("grants")
    if not isinstance(grants, list):
        return result

    filtered = [
        grant
        for grant in grants
        if isinstance(grant, dict) and _grant_privilege_set(grant) & wanted
    ]
    by_level = dict.fromkeys(_GRANT_SUMMARY_LEVELS, 0)
    by_mech = dict.fromkeys(_GRANT_MECHANISMS, 0)
    for grant in filtered:
        obj_level = grant.get("objectLevel")
        if isinstance(obj_level, str) and obj_level in by_level:
            by_level[obj_level] += 1
        mechanism = grant.get("grantMechanism")
        if isinstance(mechanism, str) and mechanism in by_mech:
            by_mech[mechanism] += 1

    return {
        **result,
        "data": {
            **data,
            "grants": filtered,
            "summary": {
                "totalGrants": len(filtered),
                "byObjectLevel": by_level,
                "byGrantMechanism": by_mech,
            },
            "filteredToPrivileges": sorted(wanted),
        },
    }


def annotate_multi_connection_advisory(
    result: dict[str, Any],
    connection_id: int | None,
) -> dict[str, Any]:
    """Surface guidance when grants span multiple connectors without connection_id."""
    if connection_id is not None or not result.get("ok"):
        return result
    data = result.get("data")
    if not isinstance(data, dict):
        return result
    grants = data.get("grants")
    if not isinstance(grants, list):
        return result

    conn_ids = sorted(
        {
            grant["connectionId"]
            for grant in grants
            if isinstance(grant, dict) and isinstance(grant.get("connectionId"), int)
        }
    )
    if len(conn_ids) <= 1:
        return result

    advisory = (
        f"Grants span {len(conn_ids)} connections {conn_ids}. "
        "Ask the user for connection_id and a narrower object_path or object_name, then retry."
    )
    existing = data.get("advisoryMessage")
    if isinstance(existing, str) and existing.strip():
        advisory = f"{existing.strip()} {advisory}"
    return {
        **result,
        "data": {
            **data,
            "multipleConnections": True,
            "connectionIds": conn_ids,
            "advisoryMessage": advisory,
        },
    }


def normalize_string_list(value: str | list[str] | None) -> list[str]:
    """Split comma-separated or list values into distinct non-blank strings."""
    if value is None:
        return []
    items = [value] if isinstance(value, str) else value
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        for part in item.split(","):
            token = part.strip()
            if token and token not in seen:
                seen.add(token)
                out.append(token)
    return out


def normalize_rdam_object_type(object_type: str | None) -> str | None:
    if object_type is None:
        return None
    normalized = object_type.strip().lower()
    if not normalized:
        return None
    if normalized == MCP_RDAM_OBJECT_TYPE_ALL:
        return MCP_RDAM_OBJECT_TYPE_ALL
    return _RDAM_OBJECT_TYPE_ALIASES.get(normalized, normalized)


def filter_user_to_objects_by_level(
    result: dict[str, Any],
    object_type: str | None,
) -> dict[str, Any]:
    """Backend user_to_objects ignores objectType; keep only the requested level (no ancestors)."""
    if not result.get("ok") or object_type is None:
        return result
    data = result.get("data")
    if not isinstance(data, dict):
        return result
    grants = data.get("grants")
    if not isinstance(grants, list):
        return result

    level = object_type.lower()
    filtered = [
        grant
        for grant in grants
        if isinstance(grant.get("objectLevel"), str)
        and grant["objectLevel"].lower() == level
    ]
    by_level = dict.fromkeys(_GRANT_SUMMARY_LEVELS, 0)
    by_mech = dict.fromkeys(_GRANT_MECHANISMS, 0)
    for grant in filtered:
        obj_level = grant.get("objectLevel")
        if isinstance(obj_level, str) and obj_level in by_level:
            by_level[obj_level] += 1
        mechanism = grant.get("grantMechanism")
        if isinstance(mechanism, str) and mechanism in by_mech:
            by_mech[mechanism] += 1

    return {
        **result,
        "data": {
            **data,
            "grants": filtered,
            "summary": {
                "totalGrants": len(filtered),
                "byObjectLevel": by_level,
                "byGrantMechanism": by_mech,
            },
            "filteredToObjectLevel": object_type,
        },
    }


_DESC_SOURCE_SYSTEM_ACCESS = (
    "Native Redshift/Snowflake/Tableau grants from RDAM harvest — not OvalEdge catalog ACLs.\n\n"
    f"Backend: GET {MCP_PATH_SOURCE_SYSTEM_ACCESS}\n\n"
    "Required: source_system (redshift|snowflake|tableau), query_direction "
    "(user_to_objects | object_to_users — infer from the question).\n"
    "Optional: username, object_path, object_type, connection_id, object_name, privileges, "
    "include_columns, resolve_all_matches. One value only for source_system, object_type, "
    "connection_id per call.\n\n"
    "Never fall back to search_catalog_assets. Do not discover connection_id. "
    "For 'what tables can user X access' with connection_id: object_type=table, omit object_path. "
    "Ambiguous table paths → present matchCandidates and ask for schema.\n\n"
    "Full rules, path formats, grant models, samples: docs://ovaledge/source_system_access_guide "
    "and native_source_access workflow prompt."
)


def validate_and_normalize_object_type(
    source_system: str,
    object_type: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Validate object_type for source_system; normalize aliases."""
    ss = source_system.strip().lower()
    normalized_type = normalize_rdam_object_type(object_type)
    if normalized_type is None:
        return None, error_payload(
            f"object_type must be one of {sorted(MCP_RDAM_OBJECT_TYPES)} or "
            f"{MCP_RDAM_OBJECT_TYPE_ALL!r} (catalog aliases oeschema/oetable/oecolumn accepted), "
            f"got {object_type!r}",
        )
    if normalized_type == MCP_RDAM_OBJECT_TYPE_ALL:
        if ss == "tableau":
            return None, error_payload(
                f"object_type={MCP_RDAM_OBJECT_TYPE_ALL!r} is not supported for tableau."
            )
        return MCP_RDAM_OBJECT_TYPE_ALL, None
    if normalized_type not in MCP_RDAM_OBJECT_TYPES:
        return None, error_payload(
            f"object_type must be one of {sorted(MCP_RDAM_OBJECT_TYPES)} "
            f"(catalog aliases oeschema/oetable/oecolumn accepted), got {object_type!r}",
        )
    if normalized_type == "column" and ss != "redshift":
        return None, error_payload("object_type=column is supported for redshift only.")
    if normalized_type in {"project", "report"} and ss != "tableau":
        return None, error_payload(
            f"object_type={normalized_type!r} is supported for tableau only.",
        )
    if normalized_type in {"database", "schema", "table", "column"} and ss == "tableau":
        return None, error_payload(
            f"object_type={normalized_type!r} is not valid for tableau; use project or report.",
        )
    return normalized_type, None


def reject_multiple_source_system(source_system: str | list[str]) -> dict[str, Any] | None:
    values = normalize_string_list(source_system)
    if len(values) > 1:
        return error_payload(MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR)
    return None


def reject_multiple_connection_id(
    connection_id: int | list[int] | None,
) -> dict[str, Any] | None:
    if isinstance(connection_id, list):
        ids = [value for value in connection_id if value is not None]
        if len(ids) > 1:
            return error_payload(MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR)
    return None


def reject_multiple_object_type(
    object_type: str | list[str] | None,
) -> dict[str, Any] | None:
    if len(normalize_string_list(object_type)) > 1:
        return error_payload(MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR)
    return None


def resolve_single_connection_id(connection_id: int | list[int] | None) -> int | None:
    if connection_id is None:
        return None
    if isinstance(connection_id, list):
        ids = [value for value in connection_id if value is not None]
        return ids[0] if ids else None
    return connection_id


def resolve_single_object_type(object_type: str | list[str] | None) -> str | None:
    values = normalize_string_list(object_type)
    return values[0] if values else None


def is_connection_wide_table_listing(
    query_direction: str,
    object_path: str | list[str] | None,
    object_type: str | list[str] | None,
    connection_id: int | list[int] | None,
) -> bool:
    """user_to_objects + table + connection_id with no object_path = all tables on connector."""
    if normalize_string_list(object_path):
        return False
    qd = query_direction.strip().lower()
    if qd != "user_to_objects":
        return False
    if resolve_single_connection_id(connection_id) is None:
        return False
    raw_type = resolve_single_object_type(object_type)
    return normalize_rdam_object_type(raw_type) == "table"


def validate_source_system_access_args(
    source_system: str | list[str],
    query_direction: str,
    username: str | list[str] | None,
    object_path: str | list[str] | None,
    object_type: str | list[str] | None,
    connection_id: int | list[int] | None,
) -> dict[str, Any] | None:
    multi_source_err = reject_multiple_source_system(source_system)
    if multi_source_err is not None:
        return multi_source_err
    multi_conn_err = reject_multiple_connection_id(connection_id)
    if multi_conn_err is not None:
        return multi_conn_err
    multi_type_err = reject_multiple_object_type(object_type)
    if multi_type_err is not None:
        return multi_type_err

    source_values = normalize_string_list(source_system)
    source = source_values[0] if source_values else str(source_system).strip()
    if source.lower() not in MCP_SOURCE_SYSTEMS:
        return error_payload(
            f"source_system must be one of {sorted(MCP_SOURCE_SYSTEMS)}, got {source!r}",
        )
    qd = query_direction.strip().lower()
    if qd not in MCP_QUERY_DIRECTIONS:
        return error_payload(
            f"query_direction must be one of {sorted(MCP_QUERY_DIRECTIONS)}, "
            f"got {query_direction!r}",
        )
    return None
