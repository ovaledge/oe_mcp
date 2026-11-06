"""Data story lookup helpers."""

from __future__ import annotations

import re
from html import unescape
from typing import Any

from server.tools.common import as_dict as _as_dict
from server.tools.common.descriptions import classify_tool_desc
from server.tools.governance._shared import _cell

# Deprecated as a standalone MCP tool — use knowledge_search. Kept for enrichment helpers.
_DESC_DATASTORY = classify_tool_desc(
    "Data-story enrichment helper (not registered as a standalone MCP tool). "
    "Use knowledge_search for dual-corpus org knowledge + platform docs."
)
def _story_zone_name(meta: dict[str, Any]) -> str:
    return _cell(meta.get("storyZoneName"))


def _story_citation(title_link: str, zone_name: str) -> str:
    """Markdown for prose: [Title](#nav/story?id=…) (story zone: Zone)."""
    title = title_link.strip()
    zone = zone_name.strip()
    if title and zone:
        return f"{title} (story zone: {zone})"
    return title or zone


def _strip_html(raw_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.I)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _parse_story_sections(story: str | None) -> list[tuple[str, str]]:
    """Split story HTML or text into (heading, body) pairs for display."""
    if not story or not str(story).strip():
        return []
    raw = str(story).strip()
    sections: list[tuple[str, str]] = []
    for match in re.finditer(
        r"<h[1-6][^>]*>\s*(.*?)\s*</h[1-6]>(.*?)(?=<h[1-6]|$)",
        raw,
        flags=re.I | re.S,
    ):
        heading = _strip_html(match.group(1))
        body = _strip_html(match.group(2))
        if heading and body:
            sections.append((heading, body))
    if sections:
        return sections
    plain = _strip_html(raw) if "<" in raw else raw.strip()
    if plain:
        return [("", plain)]
    return []


def _format_datastory_display(body: dict[str, Any]) -> str:
    """Markdown layout: storyCitation, section headings (Scope, Cadence, …), nav URL."""
    data = _as_dict(body.get("data"))
    if not data:
        return ""
    meta = _as_dict(data.get("metadata"))
    content = _as_dict(data.get("content"))
    ac = _as_dict(data.get("accessControl"))

    title_link = str(body.get("storyTitleLink") or data.get("storyTitleLink") or "").strip()
    story_name = _cell(meta.get("storyName"))
    if not title_link and story_name:
        nav = str(body.get("navLink") or data.get("navLink") or "")
        title_link = f"[{story_name}]({nav})" if nav else story_name

    zone_name = _story_zone_name(meta)
    citation = str(
        body.get("storyCitation") or data.get("storyCitation") or ""
    ).strip() or _story_citation(title_link, zone_name)

    lines: list[str] = []
    if citation:
        lines.extend([citation, ""])
    else:
        lines.extend(["Here is the data story that matches that content:", ""])

    for heading, section_body in _parse_story_sections(content.get("story")):
        if heading:
            lines.extend([f"**{heading}**", "", section_body, ""])
        else:
            lines.extend([section_body, ""])

    roles = ac.get("authorizedRoles")
    if isinstance(roles, list) and roles:
        role_str = ", ".join(_cell(r) for r in roles if r)
        if role_str:
            lines.extend(["**Access control**", "", f"- **Authorized roles:** {role_str}", ""])

    nav_url = str(body.get("navUrl") or data.get("navUrl") or "").strip()
    if nav_url:
        lines.extend(["", nav_url])

    return "\n".join(lines).rstrip()


def _enrich_datastory_response(body: dict[str, Any]) -> dict[str, Any]:
    """Add formattedResponse only; navigation URLs must come from the API unchanged."""
    if not body.get("ok"):
        return body
    formatted = _format_datastory_display(body)
    if formatted:
        body["formattedResponse"] = formatted
        data = body.get("data")
        if isinstance(data, dict):
            data["formattedResponse"] = formatted
    return body


