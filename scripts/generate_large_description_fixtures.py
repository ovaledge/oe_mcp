#!/usr/bin/env python3
"""
Generate ~5 MiB description fixtures for OvalEdge / MCP slimming tests.

Usage:
    poetry run python scripts/generate_large_description_fixtures.py
    poetry run python scripts/generate_large_description_fixtures.py --size-mib 5

Outputs under testdata/fixtures/ (gitignored):
    business-description-plain-5mb.txt   — paste into plainText / description fields
    business-description-wikitext-5mb.html — paste into wikitext / wiki HTML fields
    README.txt — how to use in OvalEdge UI
"""

from __future__ import annotations

import argparse
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUT_DIR = _REPO_ROOT / "testdata" / "fixtures"

_PLAIN_PARAGRAPH = (
    "This is synthetic governance narrative for MCP response-size testing. "
    "Line {line:06d}: tables, columns, policies, and data-quality rules should "
    "remain readable after server-side truncation to stay under the Cursor 1MB "
    "tool-result cap. OvalEdge business descriptions often grow via pasted "
    "runbooks, compliance text, and embedded documentation. "
)


def _write_plain(path: Path, target_bytes: int) -> int:
    lines: list[str] = []
    nbytes = 0
    line = 0
    while nbytes < target_bytes:
        line += 1
        row = _PLAIN_PARAGRAPH.format(line=line) + "\n"
        lines.append(row)
        nbytes += len(row.encode("utf-8"))
    text = "".join(lines)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def _write_wiki_html(path: Path, target_bytes: int) -> int:
    chunks: list[str] = [
        "<div class='oe-wiki-test'>",
        "<h1>Synthetic 5MB business description (wiki HTML)</h1>",
        "<p>Use this to test MCP <code>catalog_asset_details</code> slimming.</p>",
    ]
    nbytes = sum(len(c.encode("utf-8")) for c in chunks)
    section = 0
    while nbytes < target_bytes:
        section += 1
        block = (
            f"<section id='sec-{section}'><h2>Section {section}</h2>"
            f"<p>{'Lorem ipsum dolor sit amet. ' * 40}</p>"
            f"<ul>{''.join(f'<li>Item {section}-{i}</li>' for i in range(1, 6))}</ul>"
            f"</section>\n"
        )
        chunks.append(block)
        nbytes += len(block.encode("utf-8"))
    chunks.append("</div>")
    text = "".join(chunks)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def _write_readme(path: Path, plain_name: str, wiki_name: str, size_mib: float) -> None:
    path.write_text(
        f"""Large description test fixtures (~{size_mib:g} MiB each)

Files:
  - {plain_name}  → businessDescription.plainText or plain description field
  - {wiki_name}   → businessDescription.wikitext / HTML wiki field

How to test in OvalEdge:
  1. Pick a test table (dev/sandbox).
  2. Open Business Description in the catalog UI.
  3. Paste plain file into plain-text / wiki plain view (if supported).
  4. Paste HTML file into rich wiki / HTML editor (or API update-asset-descriptions).
  5. In Cursor, call catalog_asset_details for that object_id + object_type.

Expected after MCP slimming (oe_mcp with mcp_response_slim):
  - Tool succeeds (no "Tool result is too large")
  - businessDescription._mcpDescriptionTruncated = true
  - Text ends with "...[truncated ...]"

Regenerate:
  poetry run python scripts/generate_large_description_fixtures.py
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large description test files")
    parser.add_argument(
        "--size-mib",
        type=float,
        default=5.0,
        help="Target size per file in mebibytes (default: 5)",
    )
    args = parser.parse_args()
    target_bytes = int(args.size_mib * 1024 * 1024)
    mib_label = f"{args.size_mib:g}".replace(".", "p")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    plain_path = _OUT_DIR / f"business-description-plain-{mib_label}mb.txt"
    wiki_path = _OUT_DIR / f"business-description-wikitext-{mib_label}mb.html"

    plain_size = _write_plain(plain_path, target_bytes)
    wiki_size = _write_wiki_html(wiki_path, target_bytes)
    _write_readme(_OUT_DIR / "README.txt", plain_path.name, wiki_path.name, args.size_mib)

    def _mib(n: int) -> str:
        return f"{n / (1024 * 1024):.2f}"

    print(f"Wrote {_OUT_DIR}/")
    print(f"  {plain_path.name}  ({_mib(plain_size)} MiB)")
    print(f"  {wiki_path.name}  ({_mib(wiki_size)} MiB)")
    print("  README.txt")
    print()
    print("Paste into OvalEdge business description, then test catalog_asset_details in Cursor.")


if __name__ == "__main__":
    main()
