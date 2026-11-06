Large description test fixtures (~2 MiB each)

Files:
  - business-description-plain-2mb.txt  → businessDescription.plainText or plain description field
  - business-description-wikitext-2mb.html   → businessDescription.wikitext / HTML wiki field

How to test in OvalEdge:
  1. Pick a test table (dev/sandbox).
  2. Open Business Description in the catalog UI.
  3. Paste plain file into plain-text / wiki plain view (if supported).
  4. Paste HTML file into rich wiki / HTML editor (or API update-asset-descriptions).
  5. In Cursor, call asset_details for that object_id + object_type.

Expected after MCP slimming (oe_mcp with mcp_response_slim):
  - Tool succeeds (no "Tool result is too large")
  - businessDescription._mcpDescriptionTruncated = true
  - Text ends with "...[truncated ...]"

Regenerate:
  poetry run python scripts/generate_large_description_fixtures.py
