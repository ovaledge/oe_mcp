from fastmcp import FastMCP
from fastmcp.prompts import Message

from server.constants import (
    TOOL_COUNT_CATALOG,
    TOOL_GET_ASSET,
    TOOL_GET_LINEAGE,
    TOOL_GET_RELATIONSHIPS,
    TOOL_LOOKUP_TERM,
    TOOL_SEARCH_CATALOG,
    TOOL_SEARCH_DOCS,
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
            f"2. Call {TOOL_SEARCH_CATALOG} with those keywords\n"
            f"3. Call {TOOL_LOOKUP_TERM} for each key business concept found\n"
            f"4. Cross-reference term-associated objects against catalog results\n"
            f"5. Call {TOOL_COUNT_CATALOG} to show scope if useful\n"
            f"6. Present the top 5 recommended assets with:\n"
            f"   - Full governance context (owner, steward, certification, DQ score)\n"
            f"   - Trust summary per asset (green/yellow/red)\n"
            f"   - Business term alignment if query matched a glossary term\n"
            f"   - Flag if no relevant assets found in the catalog"
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
            f"1. Call {TOOL_LOOKUP_TERM}(query='{term}', "
            f"include_related=True, include_data_objects=True)\n"
            f"2. Traverse 'Calculates from' and 'Is synonym to' relationships one level\n"
            f"3. Call {TOOL_GET_ASSET} for the top 2 associated physical data objects\n"
            f"4. Synthesise and present:\n"
            f"   - Organisational definition (not a generic one)\n"
            f"   - Calculation formula or method if available\n"
            f"   - Related terms — synonyms, upstream calculation sources\n"
            f"   - Physical tables/columns where the term is implemented\n"
            f"   - Classifications (PII, Sensitive) if relevant\n"
            f"   - Who owns the definition (owner/steward)\n"
            f"   - Curation completeness warning if term is red-scored"
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
            f"1. Call {TOOL_SEARCH_CATALOG} to resolve the name to object_id\n"
            f"2. Call {TOOL_GET_ASSET} — certification, governance roles, "
            f"classifications, curation breakdown\n"
            f"3. Call {TOOL_GET_LINEAGE}(direction=UPSTREAM) — verify data origin\n"
            f"4. Score each trust dimension and produce a red/amber/green scorecard:\n"
            f"   - DQ Score: value + pass/fail rule count\n"
            f"   - Metadata completeness: curation band + missing components\n"
            f"   - Certification: status + certified by\n"
            f"   - Governance: owner/steward assigned? Non-admin?\n"
            f"   - Lineage: origin traceable? Auto or manual?\n"
            f"   - Sensitivity: classifications present\n"
            f"5. Overall verdict: Trusted / Use with Caution / Unreliable\n"
            f"6. Recommended action if any dimension is red"
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
            f"1. Call {TOOL_LOOKUP_TERM}(domain='{domain}') — key terms\n"
            f"2. Call {TOOL_SEARCH_CATALOG} with domain keywords "
            f"and certification_status=certified\n"
            f"3. Call {TOOL_COUNT_CATALOG} filtered to this domain\n"
            f"4. Aggregate DQ scores and curation scores across returned assets\n"
            f"5. Identify governance contacts (owners/stewards) across key assets\n"
            f"6. Present:\n"
            f"   - Domain glossary: key terms with definitions\n"
            f"   - Certified anchor datasets (top 5)\n"
            f"   - Domain quality health (avg DQ score, % certified)\n"
            f"   - Key governance contacts with roles\n"
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
            f"1. Call {TOOL_SEARCH_CATALOG} to resolve name to object_id\n"
            f"2. Call {TOOL_GET_LINEAGE}(direction=BOTH, depth=3)\n"
            f"3. For each lineage node check certification_status — surface uncertified\n"
            f"4. Call {TOOL_GET_ASSET} for the root asset and key nodes\n"
            f"5. Narrate the path in plain language: source → transformations → consumers\n"
            f"6. Present:\n"
            f"   - Narrative lineage path (source to output)\n"
            f"   - Upstream sources with lineage type (auto/manual)\n"
            f"   - Downstream consumers grouped by type (reports, tables, pipelines)\n"
            f"   - Risk flags: uncertified nodes, missing owners, cautioned assets\n"
            f"   - Total upstream and downstream counts\n"
            f"   - Recommendation if governance gaps found"
        )
        return [Message(text)]

    @mcp.prompt()
    def find_related_assets(asset_name: str) -> list[Message]:
        """
        P6 — Discover all structurally and semantically related assets.
        Tables joinable via PK/FK, assets sharing glossary terms,
        and lineage neighbours.

        Trigger: "What tables can I join with orders?"
                 "Find datasets that work alongside revenue_fact"
        """
        text = (
            f"Find all assets related to: '{asset_name}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_CATALOG} to resolve name to object_id\n"
            f"2. Call {TOOL_GET_RELATIONSHIPS} — structural joins (PK/FK)\n"
            f"3. Call {TOOL_GET_ASSET} — extract linked terms from anchor asset\n"
            f"4. Call {TOOL_LOOKUP_TERM} for each linked term — "
            f"find other objects sharing same terms\n"
            f"5. De-duplicate and rank results:\n"
            f"   (1) Direct FK relationships\n"
            f"   (2) Shared glossary term\n"
            f"   (3) Lineage neighbours\n"
            f"6. Present:\n"
            f"   - Joinable tables (FK/PK) with join column details\n"
            f"   - Semantically related assets (shared terms)\n"
            f"   - Trust indicator per related asset\n"
            f"   - Suggested analysis scenarios using the combination"
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
            f"1. Call {TOOL_SEARCH_DOCS}(query='{question}', top_k=7)\n"
            f"2. Grade relevance of returned chunks against the question\n"
            f"3. If relevant docs found:\n"
            f"   - Synthesise a step-by-step answer\n"
            f"   - Include source citations with docs.ovaledge.com URLs\n"
            f"4. If no relevant docs found:\n"
            f"   - Answer from general knowledge\n"
            f"   - Clearly label as 'General knowledge — not from OvalEdge docs'\n"
            f"5. Suggest related features where applicable"
        )
        return [Message(text)]
