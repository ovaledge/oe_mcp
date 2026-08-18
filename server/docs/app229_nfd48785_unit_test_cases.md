# Unit test cases — APP-229 / NFD-48785

Tickets: [APP-229](https://ovaledge.atlassian.net/browse/APP-229), [NFD-48785](https://ovaledge.atlassian.net/browse/NFD-48785).  
PRs: [oe_mcp#92](https://github.com/ovaledge/oe_mcp/pull/92), [oasis_repo#68094](https://bitbucket.org/ovaledgeinc/oasis_repo/pull-requests/68094).

Extra scope on these PRs: Tableau **direct user** and **site-group** grants; DAM MCP uses **`asset_explorer`** (then `asset_details`) to resolve named objects before the native DAM API.

## Ticket mapping

| Ticket | Intent | Covered by |
|--------|--------|------------|
| APP-229 | Generic `source_system_access` / registry so new RDAM connectors need minimal MCP changes; S3/Synapse out of scope | Java registry + unsupported-source tests; Python continues to catalog_access on `mcp.source.system.unsupported` |
| NFD-48785 | Bidirectional native grants for Redshift / Snowflake / Tableau; `grant_mechanism` | Mapper JUnit; Python Tableau group/role tests; Java validation + DAA |
| Extra | Tableau group + user grants | Python `test_tableau_*`; Java `SITE_GROUP` / `WORKSPACE_GROUP` mapper; Tableau project/report object types |
| Extra | `asset_explorer` for DAM object identity | Python `TestAccessExplorerResolvesViaAssetExplorerThenDam` |

## Java JUnit (`oasis_repo/oe-api`)

Class `McpGrantMechanismMapperTest` — NFD-48785 `grant_mechanism`.

| ID | Method | Assert |
|----|--------|--------|
| J-GM-01 | `blankOrNullAccessTo_mapsToDirect` | null / blank → `direct` |
| J-GM-02 | `userOrPrivilegeAccessTo_mapsToDirect` | `USER` / `PRIVILEGE` → `direct` |
| J-GM-03 | `groupAccessTo_mapsToGroup` | `GROUP`, `USER_GROUP`, Tableau `SITE_GROUP` / `WORKSPACE_GROUP` → `group` |
| J-GM-04 | `roleAndDatabaseRoleAccessTo_mapsToRole` | `ROLE`, `DATABASE_ROLE` → `role` |
| J-GM-05 | `groupTokenTakesPrecedenceOverRoleToken` | `GROUP_ROLE` → `group` |
| J-GM-06 | `unknownAccessTo_mapsToDirect` | `ACCOUNT` / `SHARE` → `direct` |

Class `McpSourceSystemAccessReadServiceTest` — APP-229 resolve validation (no JDBC grant SQL).

| ID | Method | Ticket AC |
|----|--------|-----------|
| J-RS-01 | blank / unsupported `query_direction` | NFD required direction |
| J-RS-02 | blank `source_system` | NFD required source |
| J-RS-03 | unregistered source (e.g. mysql) → `McpDamNotSupportedException` | NFD unsupported source; APP-229 registry |
| J-RS-04 | registered future RDBMS does not throw unsupported | APP-229 extensibility |
| J-RS-05 | Snowflake `column` invalid; Tableau `table` invalid; Redshift `project` invalid | NFD object levels |
| J-RS-06 | Tableau `project` / `report` accepted until DAA | Extra Tableau objects |
| J-RS-07 | DAA denied instance vs connector messages | FR: Connector DAA |
| J-RS-08 | username not found (Redshift + Tableau) | NFD not-found |
| J-RS-09 | descendants require path / connection | APP-229 scope_mode |

Not in JUnit (service comment: stubs only): JDBC expansion of Tableau `rdam_workspace_usergroup`, All Users harvest, role member expansion. Cover those in Python or integration tests.

## Python (`oe_mcp/tests`)

`tests/tools/test_source_system_access.py`

| ID | Test | Assert |
|----|------|--------|
| P-SSA-01 | Tableau `object_to_users` | Forwards Tableau path; grants include user principals |
| P-SSA-02 | Tableau `user_to_objects` group expansion | Group membership appears as `grant_mechanism=group` |
| P-SSA-03 | Tableau `user_to_objects` direct role | `grant_mechanism=role` |
| P-SSA-04 | Redshift three mechanisms passthrough | NFD Redshift AC |
| P-SSA-05 | Snowflake column rejected | NFD Snowflake levels |
| P-SSA-06 | Named object / FQN forwarding | APP-229 routing |

`tests/tools/test_access_explorer.py`

| ID | Test | Assert |
|----|------|--------|
| P-AE-01 | Known `object_id` + `object_type` | Skips `asset_explorer`; DAM only |
| P-AE-02 | Named FQN | `asset_explorer` → `asset_details` → DAM with catalog id, type, connection, path |
| P-AE-03 | `resolve_all_matches` | Multiple catalog FQNs forwarded as `objectPath` list |
| P-AE-04 | Empty catalog resolve | Still calls DAM; no catalog fallback after empty RDAM |
| P-AE-05 | `operation=source_system_access` | Requires `source_system`; native `access_intent` |

## Suggested follow-up JUnit (not implemented — needs SQL fixtures)

| ID | Scenario |
|----|----------|
| J-TB-01 | Tableau `object_to_users` on project: direct site-user + site-group members + role members |
| J-TB-02 | Tableau `user_to_objects`: user in site group inherits project/report privileges |
| J-TB-03 | Tableau All Users group aligns with `rdam_reportgroup_privilege_ext` |
| J-TB-04 | Empty grants after resolved Tableau path → harvest-not-found note, not catalog ACL |

## How to run

```text
# Java (oe-api module)
mvn -pl oe-api test -Dtest=McpGrantMechanismMapperTest,McpSourceSystemAccessReadServiceTest

# Python MCP
pytest tests/tools/test_source_system_access.py tests/tools/test_access_explorer.py
```
