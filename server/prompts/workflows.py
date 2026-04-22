from fastmcp import FastMCP
from fastmcp.prompts import Message

from server.constants import (
    TOOL_ASSET_LINEAGE,
    TOOL_CATALOG_ASSET_DETAILS,
    TOOL_COLUMN_PROFILE,
    TOOL_LOOKUP_GLOSSARY_TERM,
    TOOL_LOOKUP_TAGS,
    TOOL_SEARCH_CATALOG,
    TOOL_SEARCH_DOCS,
    TOOL_TABLE_ENTITY_RELATIONSHIPS,
)


def register(mcp: FastMCP) -> None:

    @mcp.prompt()
    def data_discovery(query: str) -> list[Message]:
        """
        P1 — Primary discovery workflow.
        Given a description of data needed, searches the catalog,
        enriches with governance context, checks glossary alignment,
        and presents a curated shortlist with trust signals.

        Trigger: "Find data about customer transactions"
                 "What tables do we have for financial reporting?"
        """
        text = (
            f"Help me find data for: '{query}'\n\n"
            f"Please follow this sequence:\n"
            f"1. Extract search keywords from the query\n"
            f"2. Call {TOOL_SEARCH_CATALOG} with search_terms as a JSON array of those keywords, "
            f"and context_query set verbatim to: '{query}' (for server vector/semantic search); "
            f"optionally set object_type to oetable, oefile, glossary, or oetag\n"
            f"3. Call {TOOL_LOOKUP_GLOSSARY_TERM} with term_name for each key business concept\n"
            f"4. Cross-reference glossary-linked objects against catalog hits\n"
            f"5. Use pagination or repeat search with filters "
            f"(owner, steward, connection) if scope is unclear\n"
            f"6. Present the top 5 recommended assets with:\n"
            f"   - Full governance context from the catalog document "
            f"(owner, steward, certification, DQ)\n"
            f"   - Trust summary per asset (green/yellow/red) where signals exist\n"
            f"   - Business term alignment if a glossary term matched\n"
            f"   - Flag if no relevant assets were found"
        )
        return [Message(text)]

    @mcp.prompt()
    def explain_business_term(term: str) -> list[Message]:
        """
        P2 — Knowledge bridge between business language and physical data.
        Returns organisational definition, relationship graph, and
        physical tables/columns that implement the term.

        Trigger: "What does churn rate mean in our org?"
                 "How do we calculate Net Revenue?"
        """
        text = (
            f"Explain the business term '{term}' as defined in our organisation.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_LOOKUP_GLOSSARY_TERM}(term_name='{term}')\n"
            f"2. Traverse related-term and synonym fields from the response one level\n"
            f"3. For up to two linked physical objects, call {TOOL_CATALOG_ASSET_DETAILS} "
            f"with object_id and object_type from the payload "
            f"(supported: oetable, oecolumn, oefile, filecolumn, oechart, chartchild, "
            f"glossary, oetag; prefer oetable/oefile for physical data)\n"
            f"4. Synthesise and present:\n"
            f"   - Organisational definition (not a generic one)\n"
            f"   - Calculation or method if described\n"
            f"   - Related terms from the glossary response\n"
            f"   - Physical tables/files where the term appears\n"
            f"   - Classifications (PII, Sensitive) if present on linked assets\n"
            f"   - Owner/steward from glossary or linked assets\n"
            f"   - Curation or quality warnings if scores indicate gaps"
        )
        return [Message(text)]

    @mcp.prompt()
    def trust_assessment(asset_name: str) -> list[Message]:
        """
        P3 — Structured trust scorecard for a data asset.
        Covers DQ score, curation completeness, certification, lineage
        health, governance role assignment, and sensitivity classifications.

        Trigger: "Is the orders table reliable?"
                 "Should I use customer_transactions for the board report?"
        """
        text = (
            f"Produce a trust assessment for the data asset: '{asset_name}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_CATALOG} with search_terms derived from '{asset_name}' "
            f"(e.g. split into tokens) to resolve object_id and object_type "
            f"(prefer oetable or oefile)\n"
            f"2. Call {TOOL_CATALOG_ASSET_DETAILS} with object_id and object_type — certification, "
            f"governance roles, classifications\n"
            f"3. If object_type is oetable or oefile, call {TOOL_ASSET_LINEAGE} with that id/type "
            f"and depth 2–3 to verify data origin\n"
            f"4. Optionally call {TOOL_COLUMN_PROFILE} for column-level statistics "
            f"(oetable/oefile only)\n"
            f"5. Score each trust dimension and produce a red/amber/green scorecard:\n"
            f"   - DQ score and rule signals if returned\n"
            f"   - Metadata completeness\n"
            f"   - Certification\n"
            f"   - Governance: owner/steward assigned\n"
            f"   - Lineage: origin traceable when lineage exists\n"
            f"   - Sensitivity: classifications present\n"
            f"6. Overall verdict: Trusted / Use with Caution / Unreliable\n"
            f"7. Recommended action if any dimension is weak"
        )
        return [Message(text)]

    @mcp.prompt()
    def explore_data_domain(domain: str) -> list[Message]:
        """
        P4 — Domain orientation and onboarding workflow.
        Returns key certified assets, governing business terms,
        domain stewards, and a quality summary for a business domain.

        Trigger: "Show me what data we have in the Finance domain"
                 "I'm new — what are the key datasets for Marketing?"
        """
        text = (
            f"Give me an overview of the '{domain}' data domain.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_CATALOG} with search_terms including '{domain}' and related "
            f"tokens, object_type=glossary for key terms; also try term-specific "
            f"{TOOL_LOOKUP_GLOSSARY_TERM} when names are known\n"
            f"2. Call {TOOL_SEARCH_CATALOG} with search_terms for domain keywords and "
            f"object_type=oetable or oefile for anchor datasets\n"
            f"3. Optionally call {TOOL_LOOKUP_TAGS} with tag_name matching the domain "
            f"if tags are used\n"
            f"4. Aggregate quality and certification signals from returned catalog documents\n"
            f"5. Identify governance contacts (owners/stewards) across key assets\n"
            f"6. Present:\n"
            f"   - Domain glossary highlights\n"
            f"   - Anchor datasets (top candidates from search)\n"
            f"   - Domain quality health from available scores\n"
            f"   - Key governance contacts\n"
            f"   - Suggested next steps for a new team member"
        )
        return [Message(text)]

    @mcp.prompt()
    def trace_data_lineage(asset_name: str) -> list[Message]:
        """
        P5 — Full lineage trace in plain language.
        Where did this data come from? Where does it go?
        Highlights uncertified or low-quality nodes in the path.

        Trigger: "Where does the revenue_fact table come from?"
                 "What reports depend on the orders table?"
        """
        text = (
            f"Trace the full data lineage for: '{asset_name}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_CATALOG} to resolve name to object_id and object_type "
            f"(oetable or oefile)\n"
            f"2. Call {TOOL_ASSET_LINEAGE}(object_id=…, object_type=…, depth=3)\n"
            f"3. For important nodes, call {TOOL_CATALOG_ASSET_DETAILS} "
            f"and flag weak certification\n"
            f"4. Narrate the path in plain language: source → transformations → consumers\n"
            f"5. Present:\n"
            f"   - Narrative lineage path\n"
            f"   - Upstream vs downstream highlights from the graph\n"
            f"   - Risk flags: uncertified nodes, missing owners, cautioned assets\n"
            f"   - Counts of neighbours if the API returns them\n"
            f"   - Recommendation if governance gaps are visible"
        )
        return [Message(text)]

    @mcp.prompt()
    def find_related_assets(asset_name: str) -> list[Message]:
        """
        P6 — Discover structurally related assets (table entity relationships)
        and semantically linked glossary context.

        Trigger: "What tables can I join with orders?"
                 "Find datasets that work alongside revenue_fact"
        """
        text = (
            f"Find all assets related to: '{asset_name}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_CATALOG} to resolve name to object_id; "
            f"if the asset is an oetable, note the numeric id\n"
            f"2. For oetable assets, call {TOOL_TABLE_ENTITY_RELATIONSHIPS}(object_id=…) "
            f"for column/pattern relationships\n"
            f"3. Call {TOOL_CATALOG_ASSET_DETAILS} for the anchor — extract glossary or "
            f"tag references from the document if present\n"
            f"4. Call {TOOL_LOOKUP_GLOSSARY_TERM} or {TOOL_LOOKUP_TAGS} for those references "
            f"when ids or names are known\n"
            f"5. De-duplicate and rank: (1) entity relationships "
            f"(2) shared glossary/tag linkage\n"
            f"6. Present join or relationship details, semantic links, and trust indicators "
            f"per related asset"
        )
        return [Message(text)]

    @mcp.prompt()
    def platform_help(question: str) -> list[Message]:
        """
        P7 — Answers questions about how OvalEdge works.
        Backed by OvalEdge documentation RAG store (docs.ovaledge.com).
        Uses retrieve-grade-generate pattern with citations.

        Trigger: "How do I create a data quality rule?"
                 "What's the difference between a steward and a custodian?"
        """
        text = (
            f"Answer this OvalEdge platform question: '{question}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_DOCS}(query='{question}', limit=7, num_candidates=128)\n"
            f"2. Grade relevance of returned chunks against the question\n"
            f"3. If relevant docs found:\n"
            f"   - Synthesise a step-by-step answer\n"
            f"   - Include source citations with docs.ovaledge.com URLs when present\n"
            f"4. If no relevant docs found:\n"
            f"   - Answer from general knowledge\n"
            f"   - Clearly label as 'General knowledge — not from OvalEdge docs'\n"
            f"5. Suggest related features where applicable"
        )
        return [Message(text)]
