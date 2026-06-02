"""Markdown/formatting for metadata drift tool responses."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote


def _build_metadata_links(
    context_header: dict[str, Any] | None, data: dict[str, Any]
) -> dict[str, str]:
    ctx = context_header or {}
    schema_id = ctx.get("schemaId")
    analysis_id = ctx.get("analysisId")
    analysis_name = (
        ctx.get("analysisName")
        or _extract_analysis_name_from_payload(data)
        or "team"
    )
    redirect_url = data.get("redirectUrl")
    if not isinstance(redirect_url, str) or "#nav/" not in redirect_url:
        return {}
    nav_base = redirect_url.split("#nav/", 1)[0] + "#nav/"
    links: dict[str, str] = {
        "objectRedirectUrl": str(data.get("objectRedirectUrl") or redirect_url)
    }
    backend_compare_schema_url = data.get("compareSchemaUrl")
    backend_object_schema_url = data.get("objectSchemaUrl")
    backend_data_change_url = data.get("dataChangeUrl")
    backend_metadata_change_url = data.get("metadataChangeUrl")
    if isinstance(backend_compare_schema_url, str) and backend_compare_schema_url:
        links["compareSchemaUrl"] = backend_compare_schema_url
    elif analysis_id is not None:
        links["compareSchemaUrl"] = (
            f"{nav_base}analysis-advancejob?srchtab=tablesummary"
            f"&deepanalysistoolid={analysis_id}&analysisName={quote(str(analysis_name))}"
        )
    if isinstance(backend_object_schema_url, str) and backend_object_schema_url:
        links["objectSchemaUrl"] = backend_object_schema_url
    elif schema_id is not None:
        links["objectSchemaUrl"] = f"{nav_base}schema?browse=summary&id={schema_id}"
    if isinstance(backend_data_change_url, str) and backend_data_change_url:
        links["dataChangeUrl"] = backend_data_change_url
    elif schema_id is not None:
        links["dataChangeUrl"] = (
            f"{nav_base}dataandmetachanges?searchTab=datachanges&startindex=0"
            "&ftrodr=%5B%7B%22action%22%3A%5B%5D%2C%22fieldName%22%3A%22schemaname%22%7D%5D"
            f"&schemaname={schema_id}"
        )
    if isinstance(backend_metadata_change_url, str) and backend_metadata_change_url:
        links["metadataChangeUrl"] = backend_metadata_change_url
    elif schema_id is not None:
        links["metadataChangeUrl"] = (
            f"{nav_base}dataandmetachanges?searchTab=metadatachanges/table&startindex=0"
            "&ftrodr=%5B%7B%22action%22%3A%5B%5D%2C%22fieldName%22%3A%22schemaname%22%7D%5D"
            f"&schemaname={schema_id}"
        )
    return links


def _extract_analysis_name_from_payload(data: dict[str, Any]) -> str | None:
    reference = data.get("crawlComparisonReference")
    if isinstance(reference, str) and reference.strip():
        return reference.strip()
    for item in data.get("notableDeltas") or []:
        if not isinstance(item, dict):
            continue
        details = item.get("details")
        if not isinstance(details, str):
            continue
        match = re.search(r"transaction\s*:\s*'([^']+)'", details, re.IGNORECASE)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


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
    ctx = data.get("contextHeader", {}) or {}
    rollup = data.get("rollup", {}) or {}
    deltas = data.get("notableDeltas", []) or []
    sorted_adds = sorted(
        (
            d
            for d in deltas
            if isinstance(d, dict)
            and isinstance(d.get("rowCountDelta"), (int, float))
            and d.get("rowCountDelta", 0) > 0
        ),
        key=lambda d: d["rowCountDelta"],
        reverse=True,
    )[:6]
    links = _build_metadata_links(ctx, data)
    largest_adds = (
        ", ".join(
            f"{d.get('tableName', '-') } (+{int(d.get('rowCountDelta', 0)):,})"
            for d in sorted_adds
        )
        or "None"
    )
    summary_table = _format_level_summary_table(rollup)
    rollup_table = _format_rollup_table(rollup)
    top_adds_table = _format_top_adds_table(sorted_adds)
    links_table = (
        _format_links_table(links, data, only_object_redirect=show_object_redirect)
        if include_links
        else ""
    )
    lines = []
    if header_title:
        lines.extend([f"**{header_title.strip()}**", ""])
    lines.extend([
        "From Transactional Data Impact Analysis "
        f"(connection {ctx.get('connection') or '-'}, "
        f"catalog schema {ctx.get('catalogSchema') or '-'}, "
        f"oes schemaid {ctx.get('schemaId') or '-'}, "
        f"analysis id {ctx.get('analysisId') or '-'}, "
        f"snapshot {ctx.get('snapshotTimestamp') or data.get('analyzedToTimestamp') or '-'}, "
        f"{ctx.get('comparisonBasis') or data.get('crawlComparisonReference') or '-'})",
        "",
        "**Summary**",
        "",
        summary_table,
        "",
        f"**Rollup for {ctx.get('catalogSchema') or '-'}**",
        "",
        rollup_table,
        "",
        "**Notable deltas**",
        f"- Largest row-count adds: {largest_adds}",
        "",
        top_adds_table,
    ])
    if include_links:
        lines.extend(
            [
                "",
                "**Useful links and references**",
                links_table,
            ]
        )
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
    data["topLargeRowCountAdds"] = sorted(
        (
            d
            for d in (data.get("notableDeltas") or [])
            if isinstance(d, dict)
            and isinstance(d.get("rowCountDelta"), (int, float))
            and d.get("rowCountDelta", 0) > 0
        ),
        key=lambda d: d["rowCountDelta"],
        reverse=True,
    )[:6]
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
