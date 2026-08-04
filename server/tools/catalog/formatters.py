"""Markdown/formatting for metadata drift tool responses."""

from __future__ import annotations

from typing import Any

# Keep agent-facing narrative small so Cursor's ~1MB tool-result cap (and the
# aggressive 2k-char string cap in mcp_response_slim) cannot chop Top row-count adds.
_MCP_COLUMN_CHANGE_LIST_CAP = 40
_MCP_TABLE_CHANGE_LIST_CAP = 60
_MCP_ROW_COUNT_CHANGE_LIST_CAP = 30
_MCP_NOTABLE_DELTA_LIST_CAP = 40
_MCP_PROPERTY_CHANGE_TABLE_CAP = 25
_MCP_COLUMN_EXAMPLE_CAP = 8


def _values_differ(previous: Any, current: Any) -> bool:
    if previous is None or current is None:
        return False
    left = str(previous).strip()
    right = str(current).strip()
    if not left or not right:
        return False
    return left.casefold() != right.casefold()


def _column_property_rows(col: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return (Property, Previous, Current) rows for a modified column."""
    rows: list[tuple[str, str, str]] = []
    prev_type = col.get("previousDataType")
    curr_type = col.get("currentDataType")
    if _values_differ(prev_type, curr_type):
        rows.append(("Data Type", str(prev_type), str(curr_type)))
    prev_len = col.get("previousLength")
    curr_len = col.get("currentLength")
    if _values_differ(prev_len, curr_len):
        rows.append(("Length", str(prev_len), str(curr_len)))
    return rows


def _format_property_previous_current_table(col: dict[str, Any]) -> str | None:
    rows = _column_property_rows(col)
    if not rows:
        return None
    table_name = str(col.get("tableName") or "-")
    column_name = str(col.get("columnName") or "-")
    lines = [
        f"#### `{table_name}.{column_name}`",
        "",
        "| Property | Previous | Current |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {prop} | {prev} | {curr} |" for prop, prev, curr in rows)
    return "\n".join(lines)


def _format_datatype_length_section(column_changes: Any) -> str | None:
    if not isinstance(column_changes, list) or not column_changes:
        return None
    blocks: list[str] = []
    matched = 0
    for col in column_changes:
        if not isinstance(col, dict):
            continue
        if str(col.get("changeType") or "").lower() != "modified":
            continue
        block = _format_property_previous_current_table(col)
        if not block:
            continue
        matched += 1
        if len(blocks) < _MCP_PROPERTY_CHANGE_TABLE_CAP:
            blocks.append(block)
    if not blocks:
        return None
    header = ["**Datatype / length changes (modified columns)**", ""]
    body = "\n\n".join(blocks)
    trailing = ""
    remaining = matched - len(blocks)
    if remaining > 0:
        trailing = f"\n\n_…and {remaining} more modified column(s) with type/length changes_"
    return "\n".join(header) + body + trailing


def _column_change_type(col: dict[str, Any]) -> str:
    return str(col.get("changeType") or "").strip().lower()


def _is_data_modified_detail(col: dict[str, Any]) -> bool:
    detail = str(col.get("detail") or "").casefold()
    return "data modified" in detail


def _column_fqn(col: dict[str, Any]) -> str | None:
    column_name = str(col.get("columnName") or "").strip()
    if not column_name:
        return None
    table_name = str(col.get("tableName") or "").strip()
    return f"{table_name}.{column_name}" if table_name else column_name


def _column_change_priority(col: dict[str, Any]) -> tuple[int, str]:
    """Prefer schema drift over deep-analysis 'Data Modified' when capping lists."""
    props = _column_property_rows(col)
    change_type = _column_change_type(col)
    fqn = (_column_fqn(col) or "").casefold()
    if any(prop == "Data Type" for prop, _, _ in props):
        return (0, fqn)
    if any(prop == "Length" for prop, _, _ in props):
        return (1, fqn)
    if change_type == "added":
        return (2, fqn)
    if change_type in {"deleted", "removed"}:
        return (3, fqn)
    if change_type == "modified" and not _is_data_modified_detail(col):
        return (4, fqn)
    return (5, fqn)


def _prioritize_column_changes(column_changes: list[Any]) -> list[Any]:
    typed = [c for c in column_changes if isinstance(c, dict)]
    other = [c for c in column_changes if not isinstance(c, dict)]
    typed.sort(key=_column_change_priority)
    return typed + other


def _unique_column_fqns(
    column_changes: Any,
    *,
    change_types: set[str],
    limit: int,
    structural_only: bool = False,
    data_modified_ok: bool = True,
) -> list[str]:
    if not isinstance(column_changes, list) or limit <= 0:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for col in column_changes:
        if not isinstance(col, dict):
            continue
        if _column_change_type(col) not in change_types:
            continue
        if structural_only and _is_data_modified_detail(col) and not _column_property_rows(col):
            continue
        if not data_modified_ok and _is_data_modified_detail(col):
            continue
        fqn = _column_fqn(col)
        if not fqn:
            continue
        key = fqn.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(fqn)
        if len(out) >= limit:
            break
    return out


def _table_level_column_add_examples(table_summaries: Any, limit: int) -> list[str]:
    """Fallback when whole tables are new and per-column add rows are absent."""
    if not isinstance(table_summaries, list) or limit <= 0:
        return []
    ranked = sorted(
        (
            t
            for t in table_summaries
            if isinstance(t, dict) and int(t.get("columnsAdded") or 0) > 0
        ),
        key=lambda t: int(t.get("columnsAdded") or 0),
        reverse=True,
    )
    out: list[str] = []
    for t in ranked:
        table_name = str(t.get("tableName") or "").strip() or "-"
        added = int(t.get("columnsAdded") or 0)
        out.append(f"`{table_name}` (+{added} columns)")
        if len(out) >= limit:
            break
    return out


def _question_column_example_intents(question: str | None) -> set[str] | None:
    """
    Which column-example buckets to emphasize from the user question.

    None = show every non-empty bucket (default for general drift questions).
    """
    if not question or not question.strip():
        return None
    q = question.strip().casefold()
    intents: set[str] = set()
    add_tokens = ("add", "added", "new column", "columns were added", "column added")
    del_tokens = ("delet", "removed", "drop", "columns were deleted", "column deleted")
    if any(tok in q for tok in add_tokens):
        intents.add("added")
    if any(tok in q for tok in del_tokens):
        intents.add("deleted")
    if any(
        tok in q
        for tok in (
            "modif",
            "changed",
            "datatype",
            "data type",
            "length",
            "alter",
            "updated column",
        )
    ):
        intents.add("modified")
    if "column" in q and not intents:
        return None
    return intents or None


def _format_example_bullet_block(title: str, items: list[str], remaining: int = 0) -> str:
    lines = [f"**{title}**", ""]
    lines.extend(f"- {item}" if item.startswith("`") else f"- `{item}`" for item in items)
    if remaining > 0:
        lines.append(f"- _…and {remaining} more_")
    return "\n".join(lines)


def _format_column_name_examples_section(
    data: dict[str, Any],
    header_title: str | None = None,
) -> str | None:
    """Named column examples so agents can answer 'which columns…' without raw dumps."""
    intents = _question_column_example_intents(header_title)
    column_changes = data.get("columnChanges")
    rollup = data.get("rollup") or {}
    blocks: list[str] = []

    want_added = intents is None or "added" in intents
    want_deleted = intents is None or "deleted" in intents
    want_modified = intents is None or "modified" in intents

    if want_added and int(rollup.get("columnsAdded") or 0) > 0:
        named = _unique_column_fqns(
            column_changes,
            change_types={"added"},
            limit=_MCP_COLUMN_EXAMPLE_CAP,
        )
        total = int(rollup.get("columnsAdded") or 0)
        if named:
            blocks.append(
                _format_example_bullet_block(
                    "Example columns added",
                    named,
                    max(0, total - len(named)),
                )
            )
        else:
            table_examples = _table_level_column_add_examples(
                data.get("tableSummaries"), _MCP_COLUMN_EXAMPLE_CAP
            )
            if table_examples:
                add_tables = sum(
                    1
                    for t in (data.get("tableSummaries") or [])
                    if isinstance(t, dict) and int(t.get("columnsAdded") or 0) > 0
                )
                rem_tables = max(0, add_tables - len(table_examples))
                lines = [
                    "**Example columns added**",
                    "",
                    f"_{total} column(s) added with new tables "
                    "(per-column names when CompareSchema lists them):_",
                    "",
                    *[f"- {item}" for item in table_examples],
                ]
                if rem_tables > 0:
                    lines.append(f"- _…and {rem_tables} more table(s)_")
                blocks.append("\n".join(lines))

    if want_deleted and int(rollup.get("columnsDeleted") or 0) > 0:
        named = _unique_column_fqns(
            column_changes,
            change_types={"deleted", "removed"},
            limit=_MCP_COLUMN_EXAMPLE_CAP,
        )
        total = int(rollup.get("columnsDeleted") or 0)
        if named:
            blocks.append(
                _format_example_bullet_block(
                    "Example columns deleted",
                    named,
                    max(0, total - len(named)),
                )
            )
        else:
            deleted_tables = [
                t
                for t in (data.get("tableSummaries") or [])
                if isinstance(t, dict) and int(t.get("columnsDeleted") or 0) > 0
            ]
            if deleted_tables:
                items = [
                    f"`{t.get('tableName') or '-'}` "
                    f"(-{int(t.get('columnsDeleted') or 0)} columns)"
                    for t in deleted_tables[:_MCP_COLUMN_EXAMPLE_CAP]
                ]
                blocks.append(
                    _format_example_bullet_block(
                        "Example columns deleted",
                        items,
                        max(0, len(deleted_tables) - len(items)),
                    )
                )

    if want_modified and int(rollup.get("columnsModified") or 0) > 0:
        structural = _unique_column_fqns(
            column_changes,
            change_types={"modified"},
            limit=_MCP_COLUMN_EXAMPLE_CAP,
            structural_only=True,
            data_modified_ok=False,
        )
        total = int(rollup.get("columnsModified") or 0)
        if structural:
            blocks.append(
                _format_example_bullet_block(
                    "Example columns modified",
                    structural,
                    max(0, total - len(structural)),
                )
            )
        else:
            data_mod = _unique_column_fqns(
                column_changes,
                change_types={"modified"},
                limit=_MCP_COLUMN_EXAMPLE_CAP,
                data_modified_ok=True,
            )
            if data_mod:
                blocks.append(
                    _format_example_bullet_block(
                        "Example columns with recent data changes",
                        data_mod,
                        max(0, total - len(data_mod)),
                    )
                )

    if not blocks:
        return None
    return "\n\n".join(blocks)


def _build_metadata_links(
    context_header: dict[str, Any] | None, data: dict[str, Any]
) -> dict[str, str]:
    ctx = context_header or {}
    schema_id = ctx.get("schemaId")
    compare_schema_id = ctx.get("compareSchemaId")
    availability = data.get("dataAvailability") or {}
    if compare_schema_id is None:
        compare_schema_id = availability.get("compareSchemaId")
    redirect_url = data.get("redirectUrl")
    nav_base: str | None = None
    if isinstance(redirect_url, str) and "#nav/" in redirect_url:
        nav_base = redirect_url.split("#nav/", 1)[0] + "#nav/"
    elif isinstance(data.get("compareSchemaUrl"), str) and "#nav/" in data["compareSchemaUrl"]:
        nav_base = data["compareSchemaUrl"].split("#nav/", 1)[0] + "#nav/"
    elif isinstance(data.get("objectSchemaUrl"), str) and "#nav/" in data["objectSchemaUrl"]:
        nav_base = data["objectSchemaUrl"].split("#nav/", 1)[0] + "#nav/"

    links: dict[str, str] = {}
    if isinstance(redirect_url, str) and redirect_url:
        links["objectRedirectUrl"] = str(data.get("objectRedirectUrl") or redirect_url)

    backend_compare_schema_url = (
        data.get("compareSchemaUrl")
        or availability.get("compareSchemaRedirectUrl")
    )
    backend_object_schema_url = data.get("objectSchemaUrl")
    backend_data_change_url = data.get("dataChangeUrl")
    backend_metadata_change_url = data.get("metadataChangeUrl")

    if isinstance(backend_compare_schema_url, str) and backend_compare_schema_url:
        links["compareSchemaUrl"] = backend_compare_schema_url
    elif nav_base and compare_schema_id is not None:
        links["compareSchemaUrl"] = (
            f"{nav_base}comparedb?srchtab=history&id={compare_schema_id}"
        )
    if isinstance(backend_object_schema_url, str) and backend_object_schema_url:
        links["objectSchemaUrl"] = backend_object_schema_url
    elif nav_base and schema_id is not None:
        links["objectSchemaUrl"] = f"{nav_base}schema?browse=summary&id={schema_id}"
    if isinstance(backend_data_change_url, str) and backend_data_change_url:
        links["dataChangeUrl"] = backend_data_change_url
    elif nav_base and schema_id is not None:
        links["dataChangeUrl"] = (
            f"{nav_base}dataandmetachanges?searchTab=datachanges&startindex=0"
            "&ftrodr=%5B%7B%22action%22%3A%5B%5D%2C%22fieldName%22%3A%22schemaname%22%7D%5D"
            f"&schemaname={schema_id}"
        )
    if isinstance(backend_metadata_change_url, str) and backend_metadata_change_url:
        links["metadataChangeUrl"] = backend_metadata_change_url
    elif nav_base and schema_id is not None:
        links["metadataChangeUrl"] = (
            f"{nav_base}dataandmetachanges?searchTab=metadatachanges/table&startindex=0"
            "&ftrodr=%5B%7B%22action%22%3A%5B%5D%2C%22fieldName%22%3A%22schemaname%22%7D%5D"
            f"&schemaname={schema_id}"
        )
    return links


def _format_rollup_table(rollup: dict[str, Any] | None) -> str:
    r = rollup or {}
    rows = [
        ("Total changes", r.get("totalChanges", 0)),
        ("Tables added", r.get("tablesAdded", 0)),
        ("Tables deleted", r.get("tablesDeleted", 0)),
        ("Tables modified", r.get("tablesModified", 0)),
        ("Columns added", r.get("columnsAdded", 0)),
        ("Columns deleted", r.get("columnsDeleted", 0)),
        ("Columns modified", r.get("columnsModified", 0)),
    ]
    lines = ["| Metric | Count |", "| --- | ---: |"]
    lines.extend(f"| {metric} | {count} |" for metric, count in rows)
    return "\n".join(lines)


def _format_kv_table(title_a: str, title_b: str, rows: list[tuple[str, str]]) -> str:
    lines = [f"| {title_a} | {title_b} |", "| --- | --- |"]
    lines.extend(f"| {k} | {v} |" for k, v in rows)
    return "\n".join(lines)


def _format_level_summary_table(rollup: dict[str, Any] | None) -> str:
    r = rollup or {}
    table_total = int(r.get("tablesAdded", 0)) + int(r.get("tablesModified", 0)) + int(
        r.get("tablesDeleted", 0)
    )
    schema_total = int(r.get("schemasAdded", 0)) + int(r.get("schemasModified", 0)) + int(
        r.get("schemasRemoved", 0)
    )
    rows = [
        ("Total changes", f"{int(r.get('totalChanges', 0))}"),
        ("Schema-level changes", f"{schema_total}"),
        (
            "Table-level changes",
            f"{table_total} ({int(r.get('tablesAdded', 0))} added, "
            f"{int(r.get('tablesModified', 0))} modified, "
            f"{int(r.get('tablesDeleted', 0))} deleted)",
        ),
        (
            "Column-level changes",
            f"{int(r.get('columnsModified', 0))} modified ({int(r.get('columnsAdded', 0))} added, "
            f"{int(r.get('columnsDeleted', 0))} deleted)",
        ),
    ]
    lines = ["| Metric | Value |", "| --- | --- |"]
    lines.extend(f"| {metric} | {value} |" for metric, value in rows)
    return "\n".join(lines)


def _format_top_adds_table(deltas: list[dict[str, Any]]) -> str:
    rows: list[tuple[str, str]] = []
    for d in deltas[:6]:
        table_name = str(d.get("tableName") or "-")
        delta = int(d.get("rowCountDelta", 0))
        redirect = str(d.get("redirectUrl") or "-")
        rows.append((table_name, f"+{delta:,} ({redirect})"))
    if not rows:
        rows.append(("None", "-"))
    return _format_kv_table("Table", "Row Delta / Redirect", rows)


def _format_top_row_count_adds_bullets(deltas: list[dict[str, Any]]) -> str:
    """User-facing bullets matching MCP agent display for top row-count growth."""
    if not deltas:
        return "- None"
    lines: list[str] = []
    for d in deltas[:6]:
        table_name = str(d.get("tableName") or "-")
        delta = int(d.get("rowCountDelta", 0))
        lines.append(f"- `{table_name}` (+{delta:,})")
    return "\n".join(lines)


def _positive_row_count_adds(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Top positive row-count deltas from notableDeltas or rowCountChanges."""
    by_table: dict[str, dict[str, Any]] = {}
    for source_key in ("notableDeltas", "rowCountChanges"):
        for d in data.get(source_key) or []:
            if not isinstance(d, dict):
                continue
            delta = d.get("rowCountDelta")
            if not isinstance(delta, (int, float)) or delta <= 0:
                continue
            table_name = str(d.get("tableName") or "")
            key = table_name.lower() or str(id(d))
            prev = by_table.get(key)
            if prev is None or int(delta) > int(prev.get("rowCountDelta") or 0):
                by_table[key] = d
    return sorted(
        by_table.values(),
        key=lambda d: int(d.get("rowCountDelta") or 0),
        reverse=True,
    )[:6]


def _cap_list_field(data: dict[str, Any], key: str, limit: int) -> None:
    value = data.get(key)
    if not isinstance(value, list) or len(value) <= limit:
        return
    data[key] = value[:limit]
    data[f"_{key}Truncated"] = True
    data[f"_{key}OriginalCount"] = len(value)


def _slim_metadata_change_lists(data: dict[str, Any]) -> None:
    """Drop bulky change arrays so slim_tool_response does not erase formattedResponse."""
    cols = data.get("columnChanges")
    if isinstance(cols, list) and cols:
        data["columnChanges"] = _prioritize_column_changes(cols)
    _cap_list_field(data, "columnChanges", _MCP_COLUMN_CHANGE_LIST_CAP)
    _cap_list_field(data, "tableChanges", _MCP_TABLE_CHANGE_LIST_CAP)
    _cap_list_field(data, "rowCountChanges", _MCP_ROW_COUNT_CHANGE_LIST_CAP)
    _cap_list_field(data, "notableDeltas", _MCP_NOTABLE_DELTA_LIST_CAP)
    # tableSummaries can mirror every table change — keep aligned with table cap.
    _cap_list_field(data, "tableSummaries", _MCP_TABLE_CHANGE_LIST_CAP)


def _format_links_table(
    links: dict[str, str],
    data: dict[str, Any],
    only_object_redirect: bool = False,
) -> str:
    def _link(label: str, url: str | None) -> str:
        if not url or url == "-":
            return "-"
        return f"[{label}]({url})"

    if only_object_redirect:
        object_redirect = links.get("objectRedirectUrl") or str(data.get("redirectUrl") or "-")
        rows = [("OvalEdge object redirect URL", _link("Open object", object_redirect))]
        return _format_kv_table("Reference", "Value", rows)

    rows = [
        ("CompareSchema", _link("CompareSchema", links.get("compareSchemaUrl"))),
        ("ObjectSchema", _link("ObjectSchema", links.get("objectSchemaUrl"))),
        ("Data change", _link("Data change", links.get("dataChangeUrl"))),
        ("Metadata change", _link("Metadata change", links.get("metadataChangeUrl"))),
        ("Crawl comparison reference", str(data.get("crawlComparisonReference", "-"))),
        ("Change summary", str(data.get("changeSummary", "-"))),
        (
            "Timestamp of analyzed crawls",
            f"{data.get('analyzedFromTimestamp', '-')} -> {data.get('analyzedToTimestamp', '-')}",
        ),
    ]
    return _format_kv_table("Reference", "Value", rows)


def _default_formatted_metadata_response(
    data: dict[str, Any],
    include_links: bool = False,
    header_title: str | None = None,
    show_object_redirect: bool = False,
) -> str:
    """
    Compact agent-facing narrative for metadata drift.

    Prefer this over the OvalEdge backend formattedResponse: the backend string
    lists every table/column change and is truncated by mcp_response_slim before
    the Top row-count adds section reaches the client.
    """
    ctx = data.get("contextHeader", {}) or {}
    rollup = data.get("rollup", {}) or {}
    fallback = data.get("fallback") or {}
    top_adds = data.get("topLargeRowCountAdds") or _positive_row_count_adds(data)
    links = data.get("usefulLinks") or _build_metadata_links(ctx, data)
    lines: list[str] = []
    if header_title:
        lines.extend([f"**{header_title.strip()}**", ""])
    if fallback.get("show") and isinstance(fallback.get("message"), str):
        lines.extend([fallback["message"], ""])

    schema = ctx.get("catalogSchema") or "-"
    lines.extend([f"## Metadata changes — {schema}", ""])
    scope_parts = []
    if ctx.get("connection"):
        scope_parts.append(f"connection {ctx['connection']}")
    if ctx.get("catalogSchema"):
        scope_parts.append(f"schema {ctx['catalogSchema']}")
    if data.get("analyzedFromTimestamp") or data.get("analyzedToTimestamp"):
        scope_parts.append(
            f"period {data.get('analyzedFromTimestamp', '-')} → "
            f"{data.get('analyzedToTimestamp', '-')}"
        )
    scope = ", ".join(scope_parts) if scope_parts else "latest crawl comparison"
    lines.append(f"**Scope:** {scope}")
    lines.append("")

    if int(rollup.get("totalChanges", 0)) == 0 and not top_adds:
        lines.append("No structural or row-count changes were found for this scope.")
    else:
        lines.extend(
            [
                "**Summary**",
                "",
                data.get("summaryTableMarkdown")
                or _format_level_summary_table(rollup),
            ]
        )
        if top_adds:
            lines.extend(
                [
                    "",
                    "**Top row-count adds**",
                    "",
                    _format_top_row_count_adds_bullets(top_adds),
                ]
            )
        property_section = data.get("datatypeLengthChangesMarkdown") or (
            _format_datatype_length_section(data.get("columnChanges"))
        )
        if property_section:
            lines.extend(["", property_section])
        examples_section = data.get("columnNameExamplesMarkdown") or (
            _format_column_name_examples_section(data, header_title=header_title)
        )
        if examples_section:
            lines.extend(["", examples_section])

    if include_links and links:
        links_table = data.get("usefulLinksTableMarkdown") or _format_links_table(
            links, data, only_object_redirect=show_object_redirect
        )
        lines.extend(["", "**Useful links**", "", links_table])
    return "\n".join(lines)


def _enhance_metadata_changes_response(
    raw: dict[str, Any],
    include_links: bool = False,
    header_title: str | None = None,
    show_object_redirect: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return raw
    data = raw.get("data")
    if not isinstance(data, dict):
        return raw
    ctx = data.get("contextHeader", {})
    # Compute narrative sections before list capping so ranking uses the full backend lists.
    data["topLargeRowCountAdds"] = _positive_row_count_adds(data)
    data["datatypeLengthChangesMarkdown"] = _format_datatype_length_section(
        data.get("columnChanges")
    )
    data["columnNameExamplesMarkdown"] = _format_column_name_examples_section(
        data, header_title=header_title
    )
    _slim_metadata_change_lists(data)
    data["usefulLinks"] = _build_metadata_links(ctx, data)
    data["summaryTableMarkdown"] = _format_level_summary_table(data.get("rollup", {}))
    data["rollupTableMarkdown"] = _format_rollup_table(data.get("rollup", {}))
    data["topLargeRowCountAddsTableMarkdown"] = _format_top_adds_table(
        data["topLargeRowCountAdds"]
    )
    data["usefulLinksTableMarkdown"] = _format_links_table(
        data["usefulLinks"],
        data,
        only_object_redirect=show_object_redirect,
    )
    # Always use the compact MCP narrative. Backend FR is too large and loses
    # Top row-count adds under Cursor / mcp_response_slim truncation.
    data["formattedResponse"] = _default_formatted_metadata_response(
        data,
        include_links=include_links,
        header_title=header_title,
        show_object_redirect=show_object_redirect,
    )
    # Required compact reference block for clients that need only key fields.
    redirect_url = str(
        data.get("redirectUrl") or data["usefulLinks"].get("objectRedirectUrl") or "-"
    )
    crawl_ref = str(data.get("crawlComparisonReference") or "-")
    change_summary = str(data.get("changeSummary") or "-")
    analyzed_from = str(data.get("analyzedFromTimestamp") or "-")
    analyzed_to = str(data.get("analyzedToTimestamp") or "-")
    data["requiredInfo"] = {
        "ovaledgeObjectRedirectUrl": redirect_url,
        "crawlComparisonReference": crawl_ref,
        "changeSummary": change_summary,
        "timestampOfAnalyzedCrawls": f"{analyzed_from} -> {analyzed_to}",
        "requiredInfoMarkdown": "\n".join(
            [
                "Required info",
                f"- OvalEdge object redirect URL: [{redirect_url}]({redirect_url})"
                if redirect_url.startswith("http")
                else f"- OvalEdge object redirect URL: {redirect_url}",
                f"- Crawl comparison reference: {crawl_ref}",
                f"- Change summary: {change_summary}",
                f"- Timestamp of analyzed crawls: {analyzed_from} -> {analyzed_to}",
            ]
        ),
    }
    # Mirror key at top-level for clients that do not traverse data.formattedResponse.
    raw["formattedResponse"] = data["formattedResponse"]
    raw["summaryTableMarkdown"] = data["summaryTableMarkdown"]
    raw["requiredInfo"] = data["requiredInfo"]
    return raw
