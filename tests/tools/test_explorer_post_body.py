"""Unit tests for live-IT asset-explorer POST body mapping."""

from tests.integration.helpers import _to_asset_explorer_post_body


def test_owner_and_server_type_stay_scalars() -> None:
    body = _to_asset_explorer_post_body(
        {"owner": "admin", "serverType": "mysql", "schemaName": "sakila", "page": 1, "limit": 10}
    )
    filters = body["filters"]
    assert filters["owner"] == "admin"
    assert filters["serverType"] == "mysql"
    assert filters["schemaName"] == "sakila"
    assert body["search"] == {"page": 1, "limit": 10}


def test_list_facets_stay_lists() -> None:
    body = _to_asset_explorer_post_body(
        {
            "tags": ["Ops"],
            "certification": ["certified"],
            "tableType": ["VIEW"],
            "searchTerms": ["customer"],
        }
    )
    assert body["search"]["searchTerms"] == ["customer"]
    assert body["filters"]["tags"] == ["Ops"]
    assert body["filters"]["certification"] == ["certified"]
    assert body["filters"]["tableType"] == ["VIEW"]


def test_native_list_search_terms() -> None:
    body = _to_asset_explorer_post_body({"searchTerms": ["customer", "order"]})
    assert body["search"]["searchTerms"] == ["customer", "order"]


def test_nested_range_filters_pass_through() -> None:
    body = _to_asset_explorer_post_body(
        {
            "objectType": "oetable",
            "filters": {
                "rating": {"min": 4.01},
                "dqIndex": {"min": 80},
                "popularity": {"min": 70},
                "nullDensity": {"eq": 6.7},
                "rowCount": {"min": 100},
                "createdDate": {"from": "2024-01-01", "to": "2024-12-31"},
            },
        }
    )
    assert body["objectType"] == "oetable"
    assert body["filters"]["rating"] == {"min": 4.01}
    assert body["filters"]["dqIndex"] == {"min": 80}
    assert body["filters"]["popularity"] == {"min": 70}
    assert body["filters"]["nullDensity"] == {"eq": 6.7}
    assert body["filters"]["rowCount"] == {"min": 100}
    assert body["filters"]["createdDate"] == {"from": "2024-01-01", "to": "2024-12-31"}
