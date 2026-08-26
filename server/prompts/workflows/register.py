from fastmcp import FastMCP
from fastmcp.prompts import Message

from server.constants import (
    MCP_ACCESS_DISAMBIGUATION_RULE_DOC,
    MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
    MCP_ACCESS_PLATFORM_NAMES_NOT_SIGNALS_DOC,
    MCP_SOURCE_SYSTEMS_DOC,
    TOOL_ACCESS_EXPLORER,
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_ASSET_LINEAGE,
    TOOL_CREATE_GLOSSARY_TERM,
    TOOL_CREATE_SERVICE_REQUEST,
    TOOL_CREATE_TAG,
    TOOL_DQ_RULE_ADVISOR,
    TOOL_DQ_RULE_MANAGER,
    TOOL_KNOWLEDGE_SEARCH,
    TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
    TOOL_UPDATE_GOVERNANCE_ROLES,
)


def register(mcp: FastMCP) -> None:

    @mcp.prompt()
    def data_discovery(query: str) -> list[Message]:
        """
        Primary discovery workflow.
        Given a description of data needed, searches the catalog,
        enriches with governance context, checks glossary alignment,
        and presents a curated shortlist with trust signals.

        Trigger: "Find data about customer transactions"
                 "What tables do we have for financial reporting?"
                 "What tables can I see/access?"
                 "What schemas/columns can I view?"
        """
        text = (
            f"Help me find data for: '{query}'\n\n"
            f"Please follow this sequence:\n"
            f"1. Extract search keywords from the query\n"
            f"2. Call {TOOL_ASSET_EXPLORER} once to find related assets: search_terms as a JSON "
            f"array of those keywords, context_query set verbatim to: '{query}'. "
            f"Omit object_type, tags, and terms unless the query clearly implies them "
            f"(e.g. \"tables\", \"columns\", \"tagged X\"); hits may be any object type "
            f"(see docs://ovaledge/asset_types)\n"
            f"3. Optionally enrich: name + object_type=glossary|oetag only when looking up a "
            f"specific term/tag entity — do not replace the open catalog search with "
            f"type-scoped calls\n"
            f"4. Shortlist top hits; call {TOOL_ASSET_DETAILS} only for chosen object_id + "
            f"object_type (not before shortlist)\n"
            f"5. Use pagination or repeat search with nested filters "
            f"(certification, tableType, rating/dqIndex ranges — "
            f"docs://ovaledge/mcp_workflows) or top-level owner, steward, connection, "
            f"or an inferred object_type if scope is unclear\n"
            f"6. If the user needs narrative or policy context (not just metadata), call "
            f"{TOOL_KNOWLEDGE_SEARCH} with the narrative question\n"
            f"7. Present the top 5 recommended assets with:\n"
            f"   - object_type and Full governance context from the catalog document "
            f"(owner, steward, certification, DQ)\n"
            f"   - Trust summary per asset (green/yellow/red) where signals exist\n"
            f"   - Business term alignment if a glossary term matched\n"
            f"   - Flag if no relevant assets were found"
        )
        return [Message(text)]

    @mcp.prompt()
    def explain_business_term(term: str) -> list[Message]:
        """
        Knowledge bridge between business language and physical data.
        Returns organisational definition, relationship graph, and
        physical tables/columns that implement the term.

        Trigger: "What does churn rate mean in our org?"
                 "How do we calculate Net Revenue?"
        """
        text = (
            f"Explain the business term '{term}' as defined in our organisation.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER}(name='{term}', object_type=glossary)\n"
            f"2. Traverse related-term and synonym fields from the response one level\n"
            f"3. For up to two linked physical objects, call {TOOL_ASSET_DETAILS} "
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
        Structured trust scorecard for a data asset.
        Covers DQ score, curation completeness, certification, lineage
        health, governance role assignment, and sensitivity classifications.

        Trigger: "Is the orders table reliable?"
                 "Should I use customer_transactions for the board report?"
        """
        text = (
            f"Produce a trust assessment for the data asset: '{asset_name}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER} with search_terms derived from '{asset_name}' "
            f"(e.g. split into tokens) to resolve object_id and object_type "
            f"(prefer oetable or oefile)\n"
            f"2. Call {TOOL_ASSET_DETAILS} with object_id and object_type — certification, "
            f"governance roles, classifications\n"
            f"3. If object_type is oetable or oefile, call {TOOL_ASSET_LINEAGE} with that id/type "
            f"and depth 2–3 to verify data origin\n"
            f"4. Asset details includes profile statistics automatically for oetable/oefile\n"
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
        Domain orientation and onboarding workflow.
        Returns key certified assets, governing business terms,
        domain stewards, and a quality summary for a business domain.

        Trigger: "Show me what data we have in the Finance domain"
                 "I'm new — what are the key datasets for Marketing?"
        """
        text = (
            f"Give me an overview of the '{domain}' data domain.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER} to find related assets: search_terms including "
            f"'{domain}' and "
            f"related tokens, context_query='{domain} domain overview'; omit object_type "
            f"so tables, files, reports, columns, and other types can match\n"
            f"2. Optionally call {TOOL_ASSET_EXPLORER}(name=…, object_type=glossary) or "
            f"object_type=oetag for known term/tag entities — do not replace step 1\n"
            f"3. Shortlist anchors; call {TOOL_ASSET_DETAILS} for chosen hits when richer "
            f"metadata is needed\n"
            f"4. Call {TOOL_KNOWLEDGE_SEARCH}(query='{domain}' domain overview) "
            f"for narrative stories or product documentation\n"
            f"5. Aggregate quality and certification signals from returned catalog documents\n"
            f"6. Identify governance contacts (owners/stewards) across key assets\n"
            f"7. Present:\n"
            f"   - Domain glossary highlights\n"
            f"   - Anchor assets by object_type (top candidates from search)\n"
            f"   - Domain quality health from available scores\n"
            f"   - Key governance contacts\n"
            f"   - Suggested next steps for a new team member"
        )
        return [Message(text)]

    @mcp.prompt()
    def trace_data_lineage(asset_name: str) -> list[Message]:
        """
        Full lineage trace in plain language.
        Where did this data come from? Where does it go?
        Highlights uncertified or low-quality nodes in the path.

        Trigger: "Where does the revenue_fact table come from?"
                 "What reports depend on the orders table?"
        """
        text = (
            f"Trace the full data lineage for: '{asset_name}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER} to resolve name to object_id and object_type "
            f"(oetable or oefile)\n"
            f"2. Call {TOOL_ASSET_LINEAGE}(object_id=…, object_type=…, depth=3)\n"
            f"3. For important nodes, call {TOOL_ASSET_DETAILS} "
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
        Discover structurally related assets (table entity relationships)
        and semantically linked glossary context.

        Trigger: "What tables can I join with orders?"
                 "Find datasets that work alongside revenue_fact"
        """
        text = (
            f"Find all assets related to: '{asset_name}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER} to find related assets: search_terms including "
            f"'{asset_name}', context_query set to the user question. "
            f"Omit object_type unless the user named a type (tables/files/columns/…); "
            f"do not default to oetable-only or to tags=/terms= exact filters\n"
            f"2. Shortlist strong hits across returned object types; then call "
            f"{TOOL_ASSET_DETAILS} for each shortlisted object_id + object_type — "
            f"relationships are included for oetable; extract glossary/tag refs if present\n"
            f"3. Optionally call {TOOL_ASSET_EXPLORER} with name + object_type=glossary|oetag "
            f"only when resolving a specific term/tag entity from those refs\n"
            f"4. De-duplicate and rank: (1) open catalog search hits (2) entity relationships "
            f"(3) shared glossary/tag linkage\n"
            f"5. Present related assets by object_type with links, join/relationship details "
            f"when present, and trust indicators"
        )
        return [Message(text)]

    @mcp.prompt()
    def organizational_knowledge(question: str) -> list[Message]:
        """
        Organizational knowledge from onboarded data stories.
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
            f"1. Call {TOOL_KNOWLEDGE_SEARCH}(query='{question}') first. "
            f"Knowledge search covers both organizational stories and product documentation.\n"
            f"2. If the answer is incomplete, refine the search wording or optionally call "
            f"{TOOL_ASSET_EXPLORER} with search_terms derived from the question and "
            f"object_type=oestory to discover related story metadata.\n"
            f"3. Present the answer using formattedResponse when returned. The first line "
            f"must be storyCitation exactly (verbatim). Do not prepend phrases like "
            f"'Based on' or 'According to' before the citation.\n"
            f"4. If multiple stories match, summarize each with its citation and navUrl; "
            f"say clearly when no entitled story matched the question.\n"
            f"5. Domain guide: docs://ovaledge/governance (Data stories)"
        )
        return [Message(text)]

    @mcp.prompt()
    def metadata_drift(scope: str) -> list[Message]:
        """
        Compare metadata changes between crawls (schema/table/column drift).

        Trigger: "What changed in CUSTOMER schema after the latest crawl?"
                 "Did any tables get added this week?"
                 "Show datatype changes in the analytics schema"
        """
        text = (
            f"Analyze metadata drift for: '{scope}'\n\n"
            f"Steps:\n"
            f"1. If the scope is an asset name, call {TOOL_ASSET_EXPLORER} to resolve "
            f"object_id, connection, and schema/table names\n"
            f"2. Call {TOOL_METADATA_CHANGES_BETWEEN_CRAWLS} with filters matching the scope "
            f"(schema, table, connection, time window, or crawl ids as supported by the tool)\n"
            f"3. Summarize adds/deletes/renames and datatype or constraint changes "
            f"from the response\n"
            f"4. If the API recommends ANALYSIS_TRANSACTION_JOB or data is incomplete, "
            f"say so clearly\n"
            f"5. Link to affected assets via {TOOL_ASSET_DETAILS} when ids are known"
        )
        return [Message(text)]

    @mcp.prompt()
    def resolve_object_access(question: str) -> list[Message]:
        """
        P9 — Disambiguate who-has-access when native/DAM/source-system signals are absent.

        Trigger: "Who has access to ORDERS?"
                 "Who has access to BUSINESS.BANKING in Snowflake?"
                 "Who can see this table?"
        Not: first-person catalog inventory without a named principal
             ("What tables can I see/access?") — use data_discovery / asset_explorer.
        Not: "I want access to Loan_Data table" / "raise an access request" —
             that files a ticket via create_service_desk_request.
        """
        text = (
            f"Answer access for: '{question}'\n\n"
            f"{MCP_ACCESS_DISAMBIGUATION_RULE_DOC}\n\n"
            f"{MCP_ACCESS_PLATFORM_NAMES_NOT_SIGNALS_DOC}\n\n"
            f"When native/DAM signals are present → native_source_access → "
            f"{TOOL_ACCESS_EXPLORER} with operation=source_system_access and "
            f"access_intent_confirmed=native. "
            f"When catalog-permissions / OE security signals are present → catalog_object_access → "
            f"{TOOL_ACCESS_EXPLORER} with operation=catalog_access and "
            f"access_intent_confirmed=catalog_acl. "
            f"When **neither** signal set is present — do **not** call any access tool; "
            f"present this message verbatim and wait for **1** or **2**:\n\n"
            f"{MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE}\n\n"
            f"After **1**: native_source_access → {TOOL_ACCESS_EXPLORER} with "
            f"operation=source_system_access and access_intent_confirmed=native. "
            f"After **2**: catalog_object_access → {TOOL_ASSET_EXPLORER} (if needed) → "
            f"{TOOL_ACCESS_EXPLORER} with operation=catalog_access and "
            f"access_intent_confirmed=catalog_acl. "
            f"When speaking to users, say catalog permissions (not ACL)."
        )
        return [Message(text)]

    @mcp.prompt()
    def native_source_access(
        source_system: str,
        question: str,
    ) -> list[Message]:
        """
        Native Redshift/Snowflake/Tableau grants (harvested RDAM), not catalog permissions.

        Trigger: "What native privileges does svc_analytics have in Redshift?"
                 "Who has DAM access to prod_db.public.orders?"
                 "Which users have source-system SELECT on the Revenue Dashboard?"
                 "What tables can I access in Redshift?" (first-person + named source)
        Not: "What tables can I see/access?" without a named principal or source —
             use data_discovery / asset_explorer.
        """
        text = (
            f"Answer native access for {source_system}: '{question}'\n\n"
            f"Prerequisite: user picked **1** (native) or the question includes native/DAM "
            f"keywords — not Snowflake/Redshift/Tableau alone — or first-person inventory "
            f"with this named source. Require a named remote username for user_to_objects "
            f"(ask if missing). If ambiguous who-has-access, use resolve_object_access first. "
            f"Generic first-person catalog inventory without a principal/source is "
            f"data_discovery / {TOOL_ASSET_EXPLORER}, not this prompt.\n\n"
            f"Steps:\n"
            f"1. Infer query_direction from the question (do not ask the user): user_to_objects "
            f"when asking what a specific user can access; object_to_users when asking who has "
            f"access to an object. For user permission questions, use user_to_objects and report "
            f"only that user's grants — never object_to_users.\n"
            f"2. Call {TOOL_ACCESS_EXPLORER} with operation=source_system_access, "
            f"source_system='{source_system}' "
            f"({MCP_SOURCE_SYSTEMS_DOC}) and query_direction inferred from the question. "
            f"For object_to_users who-has-access, set access_intent_confirmed=native. "
            f"Only source_system and query_direction are mandatory otherwise; add username, "
            f"fully_qualified_name, object_type, connection_id, or privileges when the question "
            f"supplies them. Named objects: {TOOL_ASSET_EXPLORER} this tool fills object_id, "
            f"object_type, connection_id, FQN/object_path, object_name, then DAM API. "
            f"Known object_id and object_type → DAM API only. Never fall back to "
            f"{TOOL_ASSET_EXPLORER} after RDAM is empty or errors. Pass object_path or "
            f"fully_qualified_name and object_type; add connection_id when the user provides it. "
            f"Always set "
            f"object_type explicitly with object_path — Java uses "
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
            f"contributing_role, and privileges; use summary counts when returned.\n"
            f"4. If ambiguousMatch, matchCandidates, or requiresSchemaSelection: ask the user to "
            f"disambiguate (see docs for path rules); retry with a narrower path. Do not use "
            f"resolve_all_matches unless the user wants all matches combined.\n"
            f"5. DAM inventory: use query_direction=browse with connection_id (see docs). "
            f'Scoped "who has access to all under schema" → object_to_users with '
            f"scope_mode=descendants."
        )
        return [Message(text)]

    @mcp.prompt()
    def dam_object_browse(
        connection_id: int,
        scope: str,
    ) -> list[Message]:
        """
        Browse DAM-visible objects (inventory) on a connector.

        Trigger: "List schemas in BUSINESS on connection 1000"
                 "What tables are in BUSINESS.BANKING?" (DAM / connection_id known)
                 "Show columns in ORDERS table" (DAM browse)
        Not: generic "What tables can I see?" without DAM/connection_id —
             use data_discovery / asset_explorer.
        """
        text = (
            f"Browse DAM inventory on connection {connection_id} for: '{scope}'\n\n"
            f"Prerequisite: explicit DAM browse / known connection_id (or first-person "
            f"inventory with a named source that needs DAM browse). Generic first-person "
            f"catalog inventory without DAM/connection_id → data_discovery / "
            f"{TOOL_ASSET_EXPLORER}, not this prompt.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ACCESS_EXPLORER} with operation=source_system_access, "
            f"query_direction=browse, connection_id={connection_id}. "
            f"object_type is the **child level to list**; object_path (or fully_qualified_name) "
            f"is the **parent** scope.\n"
            f"2. Routing: list databases → omit object_path, object_type=database; "
            f"list schemas in db → object_path=dbName, object_type=schema; "
            f"list tables in schema → object_path=dbName.schemaName, object_type=table; "
            f"list columns in table → object_path=dbName.schemaName.tableName, "
            f"object_type=column.\n"
            f"3. Path routing: see docs://ovaledge/mcp_workflows (Native source access — "
            f"object_path formats and DAM browse).\n"
            f"4. For access questions after browse, call {TOOL_ACCESS_EXPLORER} with "
            f"operation=source_system_access and "
            f"query_direction=user_to_objects or object_to_users."
        )
        return [Message(text)]

    @mcp.prompt()
    def catalog_object_access(question: str) -> list[Message]:
        """
        OvalEdge catalog permissions (user/role grants), not native RDAM.

        Trigger: "What OvalEdge catalog permissions does john.doe have on CUSTOMER_MASTER?"
                 "Who has catalog access to the Finance schema?"
                 "Which OE security roles provide access to this report?"
        """
        text = (
            f"Answer OvalEdge catalog access: '{question}'\n\n"
            f"Prerequisite: user picked **2** (catalog permissions) or the question includes OE "
            f"security / catalog-access keywords — not Snowflake/Redshift/Tableau alone. "
            f"If ambiguous, use resolve_object_access first. "
            f"Say **catalog permissions** to users (not ACL).\n\n"
            f"Steps:\n"
            f"1. Infer query_direction: user_to_object when asking what a specific user can do; "
            f"object_to_principals when asking who has access on an asset.\n"
            f"2. Resolve the asset with {TOOL_ASSET_EXPLORER} when the user names it; pass "
            f"object_id and object_type from the chosen hit. If multiple matches, ask the user "
            f"to pick or use matchCandidates from {TOOL_ACCESS_EXPLORER}.\n"
            f"3. Call {TOOL_ACCESS_EXPLORER} with operation=catalog_access, query_direction, "
            f"username (for user_to_object), resolved object_id+object_type, and for "
            f"object_to_principals who-has-access set access_intent_confirmed=catalog_acl.\n"
            f"4. Present metadataPermission, dataPermission, grantSources, contributingRoles, "
            f"inheritedFrom when columns/terms inherit parent catalog permissions, and "
            f"redirectUrl."
        )
        return [Message(text)]

    @mcp.prompt()
    def explain_tag(tag_name: str) -> list[Message]:
        """
        Tag definition, hierarchy, and linked assets.

        Trigger: "What is the PII tag?"
                 "Explain the Finance master tag hierarchy"
        """
        text = (
            f"Explain the governance tag '{tag_name}'.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER}(name='{tag_name}', object_type=oetag)\n"
            f"2. If not found, call {TOOL_ASSET_EXPLORER} with search_terms including "
            f"'{tag_name}' and object_type=oetag\n"
            f"3. Present tag description, master/parent hierarchy, child tags, and "
            f"stewardship from formattedResponse or returned fields\n"
            f"4. Optionally list catalog assets tagged via {TOOL_ASSET_EXPLORER} with tags filter "
            f"when the user asks what data uses this tag"
        )
        return [Message(text)]

    @mcp.prompt()
    def explain_dq_rule(rule_name: str) -> list[Message]:
        """
        Data quality rule lookup and steward context.

        Trigger: "What is the Null Data Density rule?"
                 "Who stewards the revenue completeness DQ rule?"
        """
        text = (
            f"Explain the DQ rule '{rule_name}'.\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_DQ_RULE_ADVISOR}(step=lookup, rule_name='{rule_name}')\n"
            f"2. Present rule purpose, object binding, steward, and redirectUrl from hits\n"
            f"3. Note that DQ rules are not in {TOOL_ASSET_EXPLORER}; always use "
            f"{TOOL_DQ_RULE_ADVISOR} step=lookup first\n"
            f"4. If the user wants to change steward only, mention {TOOL_UPDATE_GOVERNANCE_ROLES} "
            f"with object_type=dqrule (steward role only)"
        )
        return [Message(text)]

    @mcp.prompt()
    def create_business_glossary_term(term_name: str) -> list[Message]:
        """
        Guided glossary term creation (human-in-the-loop pickers).

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
            f"4. When placement and description are ready, call without write_confirmed_by_user "
            f"to get confirm_create preview; wait for user approval\n"
            f"5. Re-call with write_confirmed_by_user=true and the same parameters to POST\n"
            f"6. Present placementPath and navUrl from the create response\n"
            f"7. Full steps: docs://ovaledge/governance"
        )
        return [Message(text)]

    @mcp.prompt()
    def create_governance_tag(tag_name: str) -> list[Message]:
        """
        Guided tag creation (secure or open mode; human confirms placement).

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
            f"3. When placement is finalized, call without write_confirmed_by_user for "
            f"confirm_create preview; wait for user approval\n"
            f"4. Re-call with write_confirmed_by_user=true and the same placement to POST\n"
            f"5. Present formattedResponse with tag summary and nav links\n"
            f"6. OPEN/SECURE steps: docs://ovaledge/governance"
        )
        return [Message(text)]

    @mcp.prompt()
    def document_asset_descriptions(
        asset_name: str,
        intent: str,
    ) -> list[Message]:
        """
        Update business/technical descriptions on catalog assets (governed write).

        Trigger: "Document what the orders table contains"
                 "Add a business description to customer_transactions"
        """
        text = (
            f"Improve descriptions for asset '{asset_name}': {intent}\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER} to resolve object_id and object_type\n"
            f"2. Call {TOOL_ASSET_DETAILS} to read current descriptions and governance\n"
            f"3. Draft description text from the user intent — do not invent facts beyond "
            f"what the user or catalog already states\n"
            f"4. Confirm the draft with the user; call {TOOL_UPDATE_ASSET_DESCRIPTIONS} "
            f"without write_confirmed_by_user for confirm_update preview\n"
            f"5. Re-call with write_confirmed_by_user=true and the same parameters to POST\n"
            f"6. Report updatedFields or blockedFields from the response"
        )
        return [Message(text)]

    @mcp.prompt()
    def assign_governance_roles(
        asset_name: str,
        role_changes: str,
    ) -> list[Message]:
        """
        Assign or remove governance roles on catalog assets or DQ rules.

        Trigger: "Make jane.doe steward of the orders table"
                 "Remove custodian from customer_transactions"
        """
        text = (
            f"Update governance roles for '{asset_name}': {role_changes}\n\n"
            f"Steps:\n"
            f"1. If the target sounds like a DQ rule, call "
            f"{TOOL_DQ_RULE_ADVISOR} step=lookup first; "
            f"otherwise {TOOL_ASSET_EXPLORER} then {TOOL_ASSET_DETAILS}\n"
            f"2. Confirm object_id, object_type, and role_changes with the user (owner, steward, "
            f"custodian, governance_role_4–6; null removes)\n"
            f"3. Call {TOOL_UPDATE_GOVERNANCE_ROLES} without write_confirmed_by_user for "
            f"confirm_update preview; wait for user approval\n"
            f"4. Re-call with write_confirmed_by_user=true and the same role_updates to POST\n"
            f"5. Report partial_success, blockedRoles (e.g. glossary-propagated), and redirectUrl"
        )
        return [Message(text)]

    @mcp.prompt()
    def platform_help(question: str) -> list[Message]:
        """
        Answers questions about how OvalEdge works.
        Backed by OvalEdge documentation RAG store (docs.ovaledge.com).
        Uses retrieve-grade-generate pattern with citations.

        Trigger: "How do I create a data quality rule?"
                 "What's the difference between a steward and a custodian?"
        """
        text = (
            f"Answer this OvalEdge platform question: '{question}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_KNOWLEDGE_SEARCH}(query='{question}', limit=7)\n"
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
        CDE column DQ assessment (read-only recommendations).

        Trigger: "Which CDE columns need DQ rules?"
                 "Recommend DQ functions for critical data elements in Finance"
        Not: "Raise a Data Quality Rule Recommendation request" —
             that files a ticket via create_service_desk_request.
        """
        text = (
            f"Assess Critical Data Element (CDE) DQ coverage for: '{scope}'\n\n"
            f"Steps:\n"
            f"1. Call {TOOL_ASSET_EXPLORER} with search_terms from the scope and "
            f"critical_data_element=Yes (and object_type oetable/oecolumn/oefile/oefilecolumn "
            f"when narrowing)\n"
            f"2. Build objects from hits (objectId + objectType). When the user named one "
            f"column/asset, pass only that object — do not discover-all. Call "
            f"{TOOL_DQ_RULE_ADVISOR}(step=assess, discover_cde_columns=true) only when "
            f"listing all CDE columns\n"
            f"3. Call {TOOL_DQ_RULE_ADVISOR} step=assess with those objects — read-only; present "
            f"recommendedFunction, recommendedFunctionCandidates, existingRulesForFunction, "
            f"associatedToDqRule, and redirect URLs. Show every same-function rule and let the "
            f"user choose a dqruleId; purpose similarity is display order only\n"
            f"3b. If same-function rules exist → after user picks, "
            f"{TOOL_DQ_RULE_MANAGER} step=associate. Else "
            f"{TOOL_DQ_RULE_MANAGER} step=create_standard. If the user rejects candidates, "
            f"re-call {TOOL_DQ_RULE_ADVISOR} step=assess with excluded_function_names; "
            f"use preferred_function_name when they pick one. Only when no "
            f"recommendedFunction remains and the user confirms custom SQL → "
            f"{TOOL_DQ_RULE_ADVISOR} step=generate_query (never hand-write SQL)\n"
            f"4. Use {TOOL_DQ_RULE_ADVISOR} step=lookup when the user names an existing rule; "
            f"do not use {TOOL_ASSET_EXPLORER} for dqrule objects\n"
            f"5. On any error: auto-retry the last successful ladder step once; if it "
            f"still fails, ask the user whether to retry again (retry only if they say "
            f"yes, otherwise stop). Do not invent recommendedFunction names or SQL"
        )
        return [Message(text)]

    @mcp.prompt()
    def create_custom_sql_dq_workflow(user_intent: str) -> list[Message]:
        """
        P18 — CDE DQ assess, associate, and custom SQL rule creation.

        Trigger: "Create custom SQL DQ rules for CDE columns"
                 "Associate CDE columns to existing DQ rules"
        """
        text = (
            f"CDE / custom SQL DQ workflow for: {user_intent}\n\n"
            f"Steps:\n"
            f"1. If column ids are unknown, call {TOOL_ASSET_EXPLORER} with "
            f"criticalDataElement filter or search_terms for CDE columns\n"
            f"2. Call {TOOL_DQ_RULE_ADVISOR} step=assess with explicit objects for the "
            f"named assets "
            f"(discover_cde_columns=true only when listing all CDE columns)\n"
            f"3. Present every existingRulesForFunction entry; never hide a same-function rule "
            f"because its purpose differs\n"
            f"4. Ask the user to choose a dqruleId. Then confirm and call "
            f"{TOOL_DQ_RULE_MANAGER} step=associate. If they explicitly want new, call "
            f"{TOOL_DQ_RULE_MANAGER}(step=create_standard, prefer_existing_rule=false) "
            f"with confirm gate\n"
            f"5. After create, surface criteriaSource and criteriaMessage; "
            f"business_metadata_with_defaults or function_default means defaults were applied\n"
            f"6. For custom_sql workflow (only after user confirmation when no "
            f"recommendedFunction remains): {TOOL_DQ_RULE_ADVISOR} step=generate_query → use "
            f"connection_id/schema_id from formattedResponse or data.context → "
            f"{TOOL_DQ_RULE_ADVISOR} step=validate_query (confirm gate) → "
            f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql "
            f"(confirm gate) after canCreateRule is true. Pass recommended_function = "
            f"recommendedFunction from generate/assess verbatim; never invent names or "
            f"hand-write SQL. IN/NOT IN set-membership is "
            f"SQL Values Contains, not SQL Exact Value. On code_found follow "
            f"recommendedReuseAction ({TOOL_DQ_RULE_MANAGER} step=associate or "
            f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql with code_object_id)\n"
            f"7. On any error: auto-retry the last successful step once; if still "
            f"failing, ask the user whether to retry again (yes → retry; no → stop)\n"
            f"8. Ad-hoc rule lookup: {TOOL_DQ_RULE_ADVISOR} step=lookup (not asset search)"
        )
        return [Message(text)]

    @mcp.prompt()
    def create_service_desk_request(intent: str) -> list[Message]:
        """
        Create a service desk request from a catalog object (access, content change, …).

        Trigger: "I want access to Loan_Data table"
                 "I need Data Read access for Customer table"
                 "Create a content change request for Employee table"
                 "Raise a Data Quality Rule Recommendation request"
                 "I want access for Loan_Data, Employee_Details and Sales_Target"
                 "Raise an access request for these tables"
        """
        text = (
            f"Create a service request for: '{intent}'\n\n"
            f"Steps:\n"
            f"1. Infer request_type (access, content, dataquality) and object_type "
            f"(table → oetable). Map 'Data Read' / 'Data Preview' / 'Data Write' to Permission. "
            f"Do not guess object_id. This is {TOOL_CREATE_SERVICE_REQUEST}, not "
            f"{TOOL_ACCESS_EXPLORER} and not {TOOL_DQ_RULE_ADVISOR}.\n"
            f"2. Call {TOOL_ASSET_EXPLORER} to resolve each named table. For "
            f"'these tables', use the prior shortlist; if none, ask which tables.\n"
            f"3. Call {TOOL_CREATE_SERVICE_REQUEST} with request_type, object_type, "
            f"object_id, and connection filters — omit summary to look up the "
            f"Published and Active template and required fields. Present formattedResponse. "
            f"object_id accepts one id, a list, or comma-separated ids. "
            f"Multiple tables: one ticket with comma-separated object ids when Select Table "
            f"allowMultiple is true; otherwise one ticket per table.\n"
            f"4. If no Published and Active template is returned, tell the user to "
            f"publish and activate it in OvalEdge Service Desk admin, then stop. "
            f"Templates with field dependencies (dependsOn) are not used, except Tags, "
            f"Terms, Business Description, Technical Description, and Additional Fields. "
            f"If lookup fails for Depends-On fields, show that error to the user and stop. "
            f"Never publish, activate, or update template status from MCP — that is "
            f"not a legal action here, even if the user asks.\n"
            f"5. Write summary yourself. Use fieldData/defaultValue for dropdowns. "
            f"Do not ask for Requested By or Requested for User — they are the logged-in user. "
            f"Ask only for required fields with no default. Never invent Business Description, "
            f"Technical Description, tags, terms, or additional field values — ask the user; "
            f"omit them if the user skips. If the user names tags or terms, pass those names "
            f"in ticket_fields; invalid names are omitted with a warning — still create. "
            f"Additional fields are optional: present fieldData.additionalFields "
            f"(name, type, options) and collect FieldName=value only for fields they want "
            f"as custom_fields. If OvalEdge rejects a field value, show that error and ask "
            f"for a correction. If the user asks "
            f"to change a default, override it. Re-call "
            f"without write_confirmed_by_user for confirm_create preview.\n"
            f"6. After explicit approval, re-call with write_confirmed_by_user=true "
            f"and confirmation_token. Present the ticket id and redirectUrl.\n"
            f"7. Playbook: docs://ovaledge/mcp_workflows"
        )
        return [Message(text)]
