import os
from unittest.mock import AsyncMock, patch

import pytest

# Settings load on first import of server.config — set env before any server imports.
# Force values so a developer `.env` or plugins (e.g. DeepEval) cannot override unit-test mocks.
os.environ["OVALEDGE_BASE_URL"] = "https://mock.ovaledge.com"
os.environ["AUTH_MODE"] = "local"
os.environ["OVALEDGE_USER_TOKEN"] = "test-user-token"
os.environ["OVALEDGE_USER_SECRET"] = "test-user-secret"
os.environ["TELEMETRY_BACKEND"] = "none"

from server.auth.context import current_oe_jwt  # noqa: E402

# ── Sample response payloads ─────────────────────────────────────

MOCK_SEARCH_RESPONSE = {
    "results": [
        {
            "objectId": "obj-001",
            "objectType": "TABLE",
            "name": "customer_transactions",
            "owner": "jane.doe",
            "steward": "john.smith",
            "certificationStatus": "certified",
            "dqScore": 92,
            "curationScore": 85,
            "classifications": ["PII", "Financial"],
        }
    ],
    "total": 1,
    "offset": 0,
    "limit": 10,
}

MOCK_ASSET_DETAIL = {
    "objectId": "obj-001",
    "objectType": "TABLE",
    "name": "customer_transactions",
    "description": "Core transaction table for all customer purchases.",
    "owner": "jane.doe",
    "steward": "john.smith",
    "certificationStatus": "certified",
    "dqScore": 92,
    "curationScore": 85,
    "classifications": ["PII", "Financial"],
    "columns": [],
    "linkedTerms": ["term-010"],
}

MOCK_GLOSSARY_RESULT = {
    "terms": [
        {
            "termId": "term-010",
            "name": "Customer Lifetime Value",
            "definition": "Total revenue attributed to a customer over their entire relationship.",
            "domain": "Marketing",
            "status": "PUBLISHED",
            "relationships": [
                {"type": "calculates-from", "targetTermId": "term-011", "targetName": "Revenue"},
            ],
            "dataObjects": [{"objectId": "obj-001", "name": "customer_transactions"}],
        }
    ],
}

MOCK_LINEAGE_RESPONSE = {
    "rootObjectId": "obj-001",
    "nodes": [
        {"id": "obj-001", "name": "customer_transactions", "type": "TABLE", "hop": 0},
        {
            "id": "obj-002",
            "name": "raw_events",
            "type": "TABLE",
            "hop": 1,
            "direction": "UPSTREAM",
        },
    ],
    "edges": [
        {"fromId": "obj-002", "toId": "obj-001", "lineageType": "auto"},
    ],
}

MOCK_COUNT_RESPONSE = {
    "count": 42,
    "objectTypesBreakdown": {"TABLE": 30, "FILE": 8, "REPORT": 4},
    "certificationBreakdown": {"certified": 25, "cautioned": 10, "violated": 5, "inactive": 2},
}

MOCK_RELATIONSHIPS = {"relationships": [{"fromTable": "a", "toTable": "b"}]}

MOCK_DOCS_SEARCH = {
    "chunks": [{"text": "How to create a rule", "url": "https://docs.ovaledge.com/x"}]
}

MOCK_UPDATE_CDE_RESPONSE = {
    "ok": True,
    "data": {
        "status": "success",
        "results": [
            {
                "objectId": 3337,
                "objectType": "oeschema",
                "redirectUrl": "https://mock.ovaledge.com/ovaledge/#nav/schema?id=3337",
                "previousCde": "None",
                "updatedCde": "Yes",
                "cdeJustification": "Understanding CDE functionality",
            }
        ],
        "governanceSummary": {"requested": 1, "updated": 1, "blocked": 0, "noChange": 0},
        "audit": {"source": "OE-MCP", "auditReferenceIds": [101]},
    },
}


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def set_oe_jwt() -> object:
    """Set a test JWT in ContextVar for all tests."""
    token = current_oe_jwt.set("test-jwt-token-for-unit-tests")
    yield None
    current_oe_jwt.reset(token)


@pytest.fixture
def mock_oe_get() -> object:
    """
    Patch OvalEdgeClient.get to return mock data.
    """
    with patch("server.client.OvalEdgeClient.get", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_oe_post() -> object:
    """Patch OvalEdgeClient.post to return mock data."""
    with patch("server.client.OvalEdgeClient.post", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_oe_client() -> object:
    """
    Patch the shared OvalEdge client factory (tools, resources, and helpers).
    """
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "server.tools.common.runtime._client_factory",
        lambda: mock_client,
    ):
        yield mock_client
