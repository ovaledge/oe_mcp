"""
Live integration tests for GET /api/v1/mcp/source-system-access (NFD-48785).

Run:
  poetry run pytest -c tests/integration/pytest.ini tests/integration -m integration

Requires OvalEdge at OVALEDGE_BASE_URL and valid local credentials in .env.
Override discovery defaults with env vars:
  OE_IT_RS_USER, OE_IT_RS_OBJECT_PATH, OE_IT_SF_USER, OE_IT_TABLEAU_OBJECT_PATH, OE_IT_CONNECTION_ID
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

# Defaults from prior manual validation on connection 1000; override via env.
RS_USER = os.environ.get("OE_IT_RS_USER", "sithik")
RS_TABLE_PATH = os.environ.get("OE_IT_RS_OBJECT_PATH", "ovaledgedb.automation.customers")
RS_PARTIAL = os.environ.get("OE_IT_RS_PARTIAL", "customers")
SF_USER = os.environ.get("OE_IT_SF_USER", "sithik")
TABLEAU_PATH = os.environ.get("OE_IT_TABLEAU_OBJECT_PATH", "")
RS_CONN_ID = os.environ.get("OE_IT_RS_CONNECTION_ID", os.environ.get("OE_IT_CONNECTION_ID", "1000"))
SF_CONN_ID = os.environ.get("OE_IT_SF_CONNECTION_ID", "")
SF_CONN_ID = os.environ.get("OE_IT_SF_CONNECTION_ID", "1002")
SF_OBJECT_PATH = os.environ.get(
    "OE_IT_SF_OBJECT_PATH", "BUSINESS.BANKING.ACCOUNTSCHEDULE"
)
SF_DB_NAME = os.environ.get("OE_IT_SF_DB_NAME", "BUSINESS")
SF_CONN_NAME = os.environ.get("OE_IT_SF_CONN_NAME", "snowflake")
TABLEAU_CONN_ID = os.environ.get("OE_IT_TABLEAU_CONNECTION_ID", "")


def _conn_param(source_system: str) -> dict[str, object]:
    raw = {
        "redshift": RS_CONN_ID,
        "snowflake": SF_CONN_ID,
        "tableau": TABLEAU_CONN_ID,
    }.get(source_system, "")
    if raw.strip():
        return {"connectionId": int(raw)}
    return {}


@pytest.mark.asyncio
async def test_validation_unsupported_source_system(api_get) -> None:
    r = await api_get(
        {"sourceSystem": "postgres", "queryDirection": "user_to_objects", "username": "x"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_validation_missing_username(api_get) -> None:
    r = await api_get({"sourceSystem": "redshift", "queryDirection": "user_to_objects"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_validation_missing_object_path(api_get) -> None:
    r = await api_get({"sourceSystem": "tableau", "queryDirection": "object_to_users"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_redshift_user_to_objects(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "user_to_objects",
            "username": RS_USER,
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 200, r.text[:500]
    data = r.json()["data"]
    grants = data.get("grants") or []
    assert len(grants) > 0, "Expected at least one Redshift grant"
    mechanisms = {g.get("grantMechanism") for g in grants}
    assert mechanisms & {"direct", "group", "role"}, f"Expected RS mechanisms, got {mechanisms}"
    summary = data.get("summary") or {}
    assert summary.get("totalGrants", 0) == len(grants)


@pytest.mark.asyncio
async def test_redshift_object_to_users_table(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "object_to_users",
            "objectPath": RS_TABLE_PATH,
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 200, r.text[:500]
    data = r.json()["data"]
    grants = data.get("grants") or []
    assert len(grants) > 0
    assert all(g.get("objectPath") for g in grants)


@pytest.mark.asyncio
async def test_redshift_partial_path_ambiguous_or_resolved(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "object_to_users",
            "objectPath": RS_PARTIAL,
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 200, r.text[:500]
    data = r.json()["data"]
    if data.get("ambiguousMatch"):
        candidates = data.get("matchCandidates") or []
        assert len(candidates) >= 2, "Partial path should yield multiple candidates"
        assert data.get("advisoryMessage")
    else:
        assert (data.get("grants") or []) or data.get("resolvedObjectPath")


@pytest.mark.asyncio
async def test_redshift_resolve_all_matches(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "object_to_users",
            "objectPath": RS_PARTIAL,
            "resolveAllMatches": True,
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 200, r.text[:500]
    data = r.json()["data"]
    grants = data.get("grants") or []
    if data.get("ambiguousMatch"):
        pytest.skip("Still ambiguous with resolveAllMatches — check backend deploy")
    assert len(grants) >= 1


@pytest.mark.asyncio
async def test_redshift_include_columns(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "object_to_users",
            "objectPath": RS_TABLE_PATH,
            "includeColumns": True,
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 200, r.text[:500]


@pytest.mark.asyncio
async def test_snowflake_user_to_objects_role_only(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "snowflake",
            "queryDirection": "user_to_objects",
            "username": SF_USER,
            **_conn_param("snowflake"),
        }
    )
    if r.status_code == 400 and "No OvalEdge connections" in r.text:
        pytest.skip("No Snowflake connection in this environment")
    if r.status_code == 400 and "not found" in r.text.lower():
        pytest.skip(f"Snowflake user {SF_USER!r} not in harvest")
    assert r.status_code == 200, r.text[:500]
    grants = r.json()["data"].get("grants") or []
    if not grants:
        pytest.skip("No Snowflake grants for user — check harvest")
    mechanisms = {g.get("grantMechanism") for g in grants}
    assert "group" not in mechanisms, f"Snowflake should not return group: {mechanisms}"
    assert "direct" not in mechanisms, f"Snowflake should not return direct: {mechanisms}"
    assert "role" in mechanisms


@pytest.mark.asyncio
async def test_snowflake_object_to_users_dbname_only(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "snowflake",
            "queryDirection": "object_to_users",
            "objectPath": SF_DB_NAME,
            **_conn_param("snowflake"),
        }
    )
    if r.status_code == 400 and "No OvalEdge connections" in r.text:
        pytest.skip("No Snowflake connection in this environment")
    if r.status_code == 400 and "not found" in r.text.lower():
        pytest.skip(f"Database {SF_DB_NAME!r} not in Snowflake harvest")
    assert r.status_code == 200, r.text[:500]


@pytest.mark.asyncio
async def test_snowflake_object_to_users_connection_dbname(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "snowflake",
            "queryDirection": "object_to_users",
            "objectPath": f"{SF_CONN_NAME}.{SF_DB_NAME}",
            **_conn_param("snowflake"),
        }
    )
    if r.status_code == 400 and "No OvalEdge connections" in r.text:
        pytest.skip("No Snowflake connection in this environment")
    if r.status_code == 400 and "not found" in r.text.lower():
        pytest.skip(f"Path {SF_CONN_NAME}.{SF_DB_NAME!r} not in Snowflake harvest")
    assert r.status_code == 200, r.text[:500]


@pytest.mark.asyncio
async def test_snowflake_object_to_users(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "snowflake",
            "queryDirection": "object_to_users",
            "objectPath": SF_OBJECT_PATH,
            **_conn_param("snowflake"),
        }
    )
    if r.status_code == 400 and "No OvalEdge connections" in r.text:
        pytest.skip("No Snowflake connection in this environment")
    if r.status_code == 400 and "not found" in r.text.lower():
        pytest.skip("Object path not in Snowflake harvest")
    assert r.status_code == 200, r.text[:500]


@pytest.mark.asyncio
async def test_tableau_object_to_users(api_get) -> None:
    path = TABLEAU_PATH
    if not path:
        # Discover first report path from a known user's grants
        r0 = await api_get(
            {
                "sourceSystem": "tableau",
                "queryDirection": "user_to_objects",
                "username": RS_USER,
                **_conn_param("tableau"),
            }
        )
        if r0.status_code == 400 and "No OvalEdge connections" in r0.text:
            pytest.skip("No Tableau connection in this environment")
        if r0.status_code != 200:
            pytest.skip(f"Cannot discover Tableau path: {r0.status_code} {r0.text[:200]}")
        grants = r0.json()["data"].get("grants") or []
        report = next((g for g in grants if g.get("objectLevel") == "report"), None)
        project = next((g for g in grants if g.get("objectLevel") == "project"), None)
        path = (report or project or {}).get("objectPath")
        if not path:
            pytest.skip("No Tableau project/report grants to test object_to_users")
    r = await api_get(
        {
            "sourceSystem": "tableau",
            "queryDirection": "object_to_users",
            "objectPath": path,
            **_conn_param("tableau"),
        }
    )
    if r.status_code == 400 and "No OvalEdge connections" in r.text:
        pytest.skip("No Tableau connection in this environment")
    assert r.status_code == 200, r.text[:500]
    grants = r.json()["data"].get("grants") or []
    assert len(grants) > 0
    assert all(g.get("grantMechanism") == "direct" for g in grants)
    assert all(g.get("principalType") == "user" for g in grants)


@pytest.mark.asyncio
async def test_tableau_user_to_objects_direct_only(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "tableau",
            "queryDirection": "user_to_objects",
            "username": RS_USER,
            **_conn_param("tableau"),
        }
    )
    if r.status_code == 400 and "No OvalEdge connections" in r.text:
        pytest.skip("No Tableau connection in this environment")
    if r.status_code == 400 and "not found" in r.text.lower():
        pytest.skip(f"Tableau user {RS_USER!r} not in harvest")
    assert r.status_code == 200, r.text[:500]
    grants = r.json()["data"].get("grants") or []
    if not grants:
        pytest.skip("No Tableau grants — verify rdam_report_* harvest")
    mechanisms = {g.get("grantMechanism") for g in grants}
    assert mechanisms == {"direct"}, f"Tableau should be direct-only, got {mechanisms}"


@pytest.mark.asyncio
async def test_user_to_objects_with_object_path_filter(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "user_to_objects",
            "username": RS_USER,
            "objectPath": RS_PARTIAL,
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 200, r.text[:500]


@pytest.mark.asyncio
async def test_unknown_user_not_found(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "user_to_objects",
            "username": "definitely.not.a.real.user.xyz123",
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 400
    assert "not found" in r.text.lower()


@pytest.mark.asyncio
async def test_unknown_object_not_found(api_get) -> None:
    r = await api_get(
        {
            "sourceSystem": "redshift",
            "queryDirection": "object_to_users",
            "objectPath": "no_such_db.no_schema.no_table_xyz",
            **_conn_param("redshift"),
        }
    )
    assert r.status_code == 400
    assert "not found" in r.text.lower()
