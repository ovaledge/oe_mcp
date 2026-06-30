from fastmcp import FastMCP
from fastmcp.prompts import Message

from server.constants import (
    MCP_ACCESS_DISAMBIGUATION_RULE_DOC,
    MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
    MCP_SOURCE_SYSTEMS_DOC,
    TOOL_ASSESS_CDE_DQ,
    TOOL_ASSET_LINEAGE,
    TOOL_ASSOCIATE_DQ_RULE_OBJECTS,
    TOOL_CATALOG_ASSET_DETAILS,
    TOOL_COLUMN_PROFILE,
    TOOL_CREATE_DQ_RULES,
    TOOL_CREATE_GLOSSARY_TERM,
    TOOL_CREATE_TAG,
    TOOL_GET_USER_OBJECT_ACCESS,
    TOOL_LOOKUP_DATASTORY,
    TOOL_LOOKUP_DQ_RULE,
    TOOL_LOOKUP_GLOSSARY_TERM,
    TOOL_LOOKUP_TAGS,
    TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
    TOOL_SEARCH_CATALOG,
    TOOL_SEARCH_DOCS,
    TOOL_SOURCE_SYSTEM_ACCESS,
    TOOL_TABLE_ENTITY_RELATIONSHIPS,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
    TOOL_UPDATE_GOVERNANCE_ROLES,
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
            f"optionally set object_type (see docs://ovaledge/asset_types)\n"
            f"3. Call {TOOL_LOOKUP_GLOSSARY_TERM} with term_name for each key business concept\n"
            f"4. Cross-reference glossary-linked objects against catalog hits\n"
            f"5. Use pagination or repeat search with filters "
            f"(owner, steward, connection) if scope is unclear\n"
            f"6. If the user needs narrative or policy context (not just metadata), call "
            f"{TOOL_LOOKUP_DATASTORY}(content_query=…) or search with object_type=oestory, "
            f"then {TOOL_LOOKUP_DATASTORY} for formattedResponse\n"
            f"7. Present the top 5 recommended assets with:\n"
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
            f"(see docs://ovaledge/asset_types; prefer oetable/oefile for physical data)\n"
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
            f"4. Call {TOOL_LOOKUP_DATASTORY}(content_query='{domain}' domain overview) "
            f"or object_type=oestory search for domain narrative stories\n"
            f"5. Aggregate quality and certification signals from returned catalog documents\n"
            f"6. Identify governance contacts (owners/stewards) across key assets\n"
            f"7. Present:\n"
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
    def organizational_knowledge(question: str) -> list[Message]:
        """
        P8 — Organizational knowledge from onboarded data stories.
        Searches narrative content the enterprise published in OvalEdge (oestory),
        not product documentation or raw catalog metadata.

        Trigger: "What is our policy on customer PII retention?"
                 "How does Finance document revenue recognition?"
                 "Summarize the onboarding playbook for analysts"
                 "What did we write about logistics data quality?"
        """
        text = (
            f"Answer using our organization's data stories: '{question}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_LOOKUP_DATASTORY}(content_query='{question}') first. "
            f"If the user named a story zone or title, also pass story_zone_name "
            f"and/or story_name to narrow the search.\n"
            f"2. If no story is found (404) or the answer is incomplete, optionally call "
            f"{TOOL_SEARCH_CATALOG} with search_terms derived from the question and "
            f"object_type=oestory to discover story object ids, then call "
            f"{TOOL_LOOKUP_DATASTORY} again with object_id or a refined content_query "
            f"(or read ovaledge://governance/data-story/{{object_id}} for the catalog document).\n"
            f"3. Do not use {TOOL_SEARCH_DOCS} for this workflow — that is for OvalEdge "
            f"product documentation only.\n"
            f"4. Present the answer using formattedResponse from the lookup. The first line "
            f"must be storyCitation exactly (verbatim). Do not prepend phrases like "
            f"'Based on' or 'According to' before the citation.\n"
            f"5. If multiple stories match, summarize each with its citation and navUrl; "
            f"say clearly when no entitled story matched the question."
        )
        return [Message(text)]

    @mcp.prompt()
    def metadata_drift(scope: str) -> list[Message]:
        """
        P9 — Compare metadata changes between crawls (schema/table/column drift).

        Trigger: "What changed in CUSTOMER schema after the latest crawl?"
                 "Did any tables get added this week?"
                 "Show datatype changes in the analytics schema"
        """
        text = (
            f"Analyze metadata drift for: '{scope}'\n\n"
            f"Steps:\n"
            f"1. If the scope is an asset name, call {TOOL_SEARCH_CATALOG} to resolve "
            f"object_id, connection, and schema/table names\n"
            f"2. Call {TOOL_METADATA_CHANGES_BETWEEN_CRAWLS} with filters matching the scope "
            f"(schema, table, connection, time window, or crawl ids as supported by the tool)\n"
            f"3. Summarize adds/deletes/renames and datatype or constraint changes "
            f"from the response\n"
            f"4. If the API recommends ANALYSYS_TRANSACTION_JOB or data is incomplete, "
            f"say so clearly\n"
            f"5. Link to affected assets via {TOOL_CATALOG_ASSET_DETAILS} when ids are known"
        )
        return [Message(text)]

    @mcp.prompt()
    def resolve_object_access(question: str) -> list[Message]:
        """
        P9 — Disambiguate who-has-access when native/DAM/source-system signals are absent.

        Trigger: "Who has access to ORDERS?"
                 "Who can see this table?"
        """
        text = (
            f"Answer access for: '{question}'\n\n"
            f"{MCP_ACCESS_DISAMBIGUATION_RULE_DOC}\n\n"
            f"When native/DAM signals are present → native_source_access → "
            f"{TOOL_SOURCE_SYSTEM_ACCESS}. Otherwise present this message verbatim and "
            f"wait for **1** or **2**:\n\n"
            f"{MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE}\n\n"
            f"After **1**: native_source_access → {TOOL_SOURCE_SYSTEM_ACCESS} with "
            f"access_intent_confirmed=native. "
            f"After **2**: catalog_object_access → {TOOL_SEARCH_CATALOG} (if needed) → "
            f"{TOOL_GET_USER_OBJECT_ACCESS} with access_intent_confirmed=catalog_acl."
        )
        return [Message(text)]

    @mcp.prompt()
    def native_source_access(
        source_system: str,
        question: str,
    ) -> list[Message]:
        """
        P10 — Native Redshift/Snowflake/Tableau grants (harvested RDAM), not catalog ACLs.

        Trigger: "What can svc_analytics SELECT in Redshift?"
                 "Who has access to prod_db.public.orders?"
                 "Which users can view the Revenue Dashboard in Tableau?"
        """
        text = (
            f"Answer native access for {source_system}: '{question}'\n\n"
            f"Steps:\n"
            f"1. Infer query_direction from the question (do not ask the user): user_to_objects "
            f"when asking what a specific user can access; object_to_users when asking who has "
            f"access to an object. For user permission questions, use user_to_objects and report "
            f"only that user's grants — never object_to_users.\n"
            f"2. Call {TOOL_SOURCE_SYSTEM_ACCESS} with source_system='{source_system}' "
            f"({MCP_SOURCE_SYSTEMS_DOC}) and query_direction inferred from the question. "
            f"Only those two fields are mandatory; add username, object_path, object_name, "
            f"fully_qualified_name, object_type, connection_id, or privileges when the question "
            f"supplies them. Always set object_type explicitly with object_path — Java uses "
            f"objectType for resolution, not dot segment count alone. Path matrix: "
            f"database=dbName; schema=dbName.schemaName or schemaName; "
            f"table=dbName.schemaName.tableName, schemaName.tableName, or tableName; "
            f"column=full four-part path or partial tableName.columnName / columnName. "
            f"fully_qualified_name is an alias for object_path when catalog gives a dotted FQN. "
            f"object_name composes with object_path for table lookups (prod_db + orders). "
            f"object_type=table limits to tables; object_type=all returns every level "
            f"(Snowflake/Redshift user_to_objects). privileges filters write checks "
            f"(INSERT/UPDATE). Prefer connection_id; use connectionName. path prefix only when "
            f"names collide. If multiple connectionIds return without connection_id, "
            f"ask the user for connection_id and a narrower path.\n"
            f"3. Present grants with grant_mechanism (direct/group/role), contributing_group, "
            f"contributing_role, and privileges; use summary counts when returned. "
            f"Java returns all harvested roles from RDAM MySQL (no system-role filter). "
            f"object_to_users includes parent hierarchy; user_to_objects is exact level only.\n"
            f"4. RDAM only — not OvalEdge catalog ACLs and not search_catalog_assets "
            f"(no Elasticsearch). If empty or error: report RDAM outcome; suggest harvest, "
            f"DAA, path/type, or native SHOW GRANTS — never call catalog search as fallback\n"
            f"5. Table without schema: pass table name (or dbName.table) only; never guess schema. "
            f"If ambiguousMatch, requiresSchemaSelection, or multiple matchCandidates, list schema "
            f"options and ask the user to pick one, then retry with dbName.schema.table. Do not "
            f"use resolve_all_matches unless the user wants all matches combined\n"
            f"6. Other partial paths: explain matchCandidates or ask the user to disambiguate\n"
            f"7. DAM inventory (list schemas/tables/columns in DAM): use "
            f"{TOOL_SOURCE_SYSTEM_ACCESS} with query_direction=browse, connection_id; "
            f"object_path is parent scope, object_type "
            f"is child level to list (omit parent + object_type=database for databases; dbName + "
            f"schema for schemas; dbName.schemaName + table for tables). Scoped \"who has access "
            f"to all under schema\" → object_to_users with scope_mode=descendants"
        )
        return [Message(text)]

    @mcp.prompt()
    def dam_object_browse(
        connection_id: int,
        scope: str,
    ) -> list[Message]:
        """
        P10b — Browse DAM-visible objects (inventory) on a connector.

        Trigger: "List schemas in BUSINESS on connection 1000"
                 "What tables are in BUSINESS.BANKING?"
                 "Show columns in ORDERS table"
        """
        text = (
            f"Browse DAM inventory on connection {connection_id} for: '{scope}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SOURCE_SYSTEM_ACCESS} with query_direction=browse, "
            f"connection_id={connection_id}. "
            f"object_type is the **child level to list**; object_path (or fully_qualified_name) "
            f"is the **parent** scope.\n"
            f"2. Routing: list databases → omit object_path, object_type=database; "
            f"list schemas in db → object_path=dbName, object_type=schema; "
            f"list tables in schema → object_path=dbName.schemaName, object_type=table; "
            f"list columns in table → object_path=dbName.schemaName.tableName, "
            f"object_type=column.\n"
            f"3. Path routing: see docs://ovaledge/mcp_workflows (Native source access — "
            f"object_path formats and DAM browse).\n"
            f"4. For access questions after browse, call "
            f"{TOOL_SOURCE_SYSTEM_ACCESS} — do not use search_catalog_assets as fallback."
        )
        return [Message(text)]

    @mcp.prompt()
    def catalog_object_access(question: str) -> list[Message]:
        """
        P10b — OvalEdge catalog ACL permissions (user/role grants), not native RDAM.

        Trigger: "What access does john.doe have on CUSTOMER_MASTER?"
                 "Who has access to the Finance schema?"
                 "Which roles provide access to this report?"
        """
        text = (
            f"Answer OvalEdge catalog access: '{question}'\n\n"
            f"Steps:\n"
            f"1. Infer query_direction: user_to_object when asking what a specific user can do; "
            f"object_to_principals when asking who has access on an asset.\n"
            f"2. Resolve the asset with {TOOL_SEARCH_CATALOG} when the user names it; pass "
            f"object_id and object_type from the chosen hit. If multiple matches, ask the user "
            f"to pick or use matchCandidates from get_user_object_access.\n"
            f"3. Call {TOOL_GET_USER_OBJECT_ACCESS} with query_direction, username (for "
            f"user_to_object), and resolved object_id+object_type.\n"
            f"4. Present metadataPermission, dataPermission, grantSources, contributingRoles, "
            f"inheritedFrom when columns/terms inherit parent ACLs, and redirectUrl.\n"
            f"5. Catalog ACL only — not native DB grants. Use {TOOL_SOURCE_SYSTEM_ACCESS} for "
            f"Redshift/Snowflake/Tableau native privileges."
        )
        return [Message(text)]

    @mcp.prompt()
    def explain_tag(tag_name: str) -> list[Message]:
        """
        P11 — Tag definition, hierarchy, and linked assets.

        Trigger: "What is the PII tag?"
                 "Explain the Finance master tag hierarchy"
        """
        text = (
            f"Explain the governance tag '{tag_name}'.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_LOOKUP_TAGS}(tag_name='{tag_name}') — add "
            f"include_parent=true and/or include_children=true when the user asks for "
            f"parent or child tags in the hierarchy\n"
            f"2. If not found, call {TOOL_SEARCH_CATALOG} with search_terms including "
            f"'{tag_name}' and object_type=oetag\n"
            f"3. Present tag description, master/parent hierarchy, child tags, and "
            f"stewardship from formattedResponse or returned fields\n"
            f"4. Optionally list catalog assets tagged via {TOOL_SEARCH_CATALOG} with tags filter "
            f"when the user asks what data uses this tag"
        )
        return [Message(text)]

    @mcp.prompt()
    def explain_dq_rule(rule_name: str) -> list[Message]:
        """
        P12 — Data quality rule lookup and steward context.

        Trigger: "What is the Null Data Density rule?"
                 "Who stewards the revenue completeness DQ rule?"
        """
        text = (
            f"Explain the DQ rule '{rule_name}'.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_LOOKUP_DQ_RULE}(rule_name='{rule_name}')\n"
            f"2. Present rule purpose, object binding, steward, and redirectUrl from hits\n"
            f"3. Note that DQ rules are not in {TOOL_SEARCH_CATALOG}; always use "
            f"{TOOL_LOOKUP_DQ_RULE} first\n"
            f"4. If the user wants to change steward only, mention {TOOL_UPDATE_GOVERNANCE_ROLES} "
            f"with object_type=dqrule (steward role only)"
        )
        return [Message(text)]

    @mcp.prompt()
    def create_business_glossary_term(term_name: str) -> list[Message]:
        """
        P13 — Guided glossary term creation (human-in-the-loop pickers).

        Trigger: "Create a glossary term Customer Lifetime Value under Finance"
                 "Add term Net Revenue with description ..."
        """
        text = (
            f"Create business glossary term '{term_name}' with user approval at each step.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_CREATE_GLOSSARY_TERM}(term_name='{term_name}') — domain picker; "
            f"if user gave domain by name, pass domain_name on the first call\n"
            f"2. Present every formattedResponse verbatim; wait for user domain_id, category, "
            f"and description — never invent description or auto-pick ids\n"
            f"3. Use skip_category / skip_subcategory only with paired *_skip_confirmed flags "
            f"after the user explicitly skips a picker\n"
            f"4. When placement and description are ready, call without create_confirmed_by_user "
            f"to get confirm_create preview; wait for user approval\n"
            f"5. Re-call with create_confirmed_by_user=true and the same parameters to POST\n"
            f"6. Present placementPath and navUrl from the create response"
        )
        return [Message(text)]

    @mcp.prompt()
    def create_governance_tag(tag_name: str) -> list[Message]:
        """
        P14 — Guided tag creation (secure or open mode; human confirms placement).

        Trigger: "Create tag Logistics"
                 "Add a confidential tag under the Finance master"
        """
        text = (
            f"Create governance tag '{tag_name}' with user approval at each step.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_CREATE_TAG}(tag_name='{tag_name}') only — show master (secure) or "
            f"parent (open) pickers; never POST on this call\n"
            f"2. Present formattedResponse and userSelectableMasters/userSelectableParents; "
            f"wait for explicit user choice with *_confirmed_by_user and "
            f"parent_step_completed_by_user flags\n"
            f"3. When placement is finalized, call without create_confirmed_by_user for "
            f"confirm_create preview; wait for user approval\n"
            f"4. Re-call with create_confirmed_by_user=true and the same placement to POST\n"
            f"5. Present formattedResponse with tag summary and nav links"
        )
        return [Message(text)]

    @mcp.prompt()
    def document_asset_descriptions(
        asset_name: str,
        intent: str,
    ) -> list[Message]:
        """
        P15 — Update business/technical descriptions on catalog assets (governed write).

        Trigger: "Document what the orders table contains"
                 "Add a business description to customer_transactions"
        """
        text = (
            f"Improve descriptions for asset '{asset_name}': {intent}\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_CATALOG} to resolve object_id and object_type\n"
            f"2. Call {TOOL_CATALOG_ASSET_DETAILS} to read current descriptions and governance\n"
            f"3. Draft description text from the user intent — do not invent facts beyond "
            f"what the user or catalog already states\n"
            f"4. Confirm the draft with the user; call {TOOL_UPDATE_ASSET_DESCRIPTIONS} "
            f"without create_confirmed_by_user for confirm_update preview\n"
            f"5. Re-call with create_confirmed_by_user=true and the same parameters to POST\n"
            f"6. Report updatedFields or blockedFields from the response"
        )
        return [Message(text)]

    @mcp.prompt()
    def assign_governance_roles(
        asset_name: str,
        role_changes: str,
    ) -> list[Message]:
        """
        P16 — Assign or remove governance roles on catalog assets or DQ rules.

        Trigger: "Make jane.doe steward of the orders table"
                 "Remove custodian from customer_transactions"
        """
        text = (
            f"Update governance roles for '{asset_name}': {role_changes}\n\n"
            f"Steps:\n"
            f"1. If the target sounds like a DQ rule, call {TOOL_LOOKUP_DQ_RULE} first; "
            f"otherwise {TOOL_SEARCH_CATALOG} then {TOOL_CATALOG_ASSET_DETAILS}\n"
            f"2. Confirm object_id, object_type, and role_changes with the user (owner, steward, "
            f"custodian, governance_role_4–6; null removes)\n"
            f"3. Call {TOOL_UPDATE_GOVERNANCE_ROLES} without create_confirmed_by_user for "
            f"confirm_update preview; wait for user approval\n"
            f"4. Re-call with create_confirmed_by_user=true and the same role_updates to POST\n"
            f"5. Report partial_success, blockedRoles (e.g. glossary-propagated), and redirectUrl"
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

    @mcp.prompt()
    def assess_cde_dq_coverage(scope: str) -> list[Message]:
        """
        P17 — CDE column DQ assessment (read-only recommendations).

        Trigger: "Which CDE columns need DQ rules?"
                 "Recommend DQ functions for critical data elements in Finance"
        """
        text = (
            f"Assess Critical Data Element (CDE) DQ coverage for: '{scope}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_SEARCH_CATALOG} with search_terms from the scope and "
            f"critical_data_element=Yes (and object_type oetable/oecolumn/oefile/oefilecolumn "
            f"when narrowing)\n"
            f"2. Build objects from hits (objectId + objectType) or call "
            f"{TOOL_ASSESS_CDE_DQ}(discover_cde_columns=true) when listing all CDE columns\n"
            f"3. Call {TOOL_ASSESS_CDE_DQ} with those objects — read-only; present "
            f"recommendedFunction, recommendedRule, associatedToDqRule, and redirect URLs\n"
            f"4. Use {TOOL_LOOKUP_DQ_RULE} when the user names an existing rule; do not use "
            f"{TOOL_SEARCH_CATALOG} for dqrule objects\n"
            f"5. Only after explicit user approval for writes: {TOOL_ASSOCIATE_DQ_RULE_OBJECTS} "
            f"for a known data quality rule id, or {TOOL_CREATE_DQ_RULES} "
            f"to create/associate in one step"
        )
        return [Message(text)]
