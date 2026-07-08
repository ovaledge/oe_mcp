"""Tests for OTLP telemetry configuration."""

from __future__ import annotations

import base64

import pytest

from server.config import Settings
from server.telemetry.setup import resolve_otlp_export


def test_resolve_otlp_export_none() -> None:
    settings = Settings(telemetry_backend="none")
    assert resolve_otlp_export(settings) is None


def test_resolve_otlp_export_phoenix_default() -> None:
    settings = Settings(
        telemetry_backend="phoenix",
        phoenix_host="http://localhost:6006",
        telemetry_service_name="oe-mcp",
        telemetry_project_name="",
        phoenix_api_key="",
    )
    endpoint, headers = resolve_otlp_export(settings)
    assert endpoint == "http://localhost:6006/v1/traces"
    assert headers == {"x-project-name": "oe-mcp"}


def test_resolve_otlp_export_phoenix_with_api_key() -> None:
    settings = Settings(
        telemetry_backend="phoenix",
        phoenix_host="http://phoenix:6006",
        phoenix_api_key="secret-key",
        telemetry_project_name="my-project",
    )
    endpoint, headers = resolve_otlp_export(settings)
    assert endpoint == "http://phoenix:6006/v1/traces"
    assert headers == {
        "Authorization": "Bearer secret-key",
        "x-project-name": "my-project",
    }


def test_resolve_otlp_export_langfuse() -> None:
    settings = Settings(
        telemetry_backend="langfuse",
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
    )
    endpoint, headers = resolve_otlp_export(settings)
    assert endpoint == "http://localhost:3000/api/public/otel/v1/traces"
    expected = base64.b64encode(b"pk-lf-test:sk-lf-test").decode("ascii")
    assert headers == {"Authorization": f"Basic {expected}"}


def test_resolve_otlp_export_langfuse_missing_keys() -> None:
    settings = Settings(
        telemetry_backend="langfuse",
        langfuse_public_key="",
        langfuse_secret_key="",
    )
    with pytest.raises(ValueError, match="LANGFUSE_PUBLIC_KEY"):
        resolve_otlp_export(settings)


def test_resolve_otlp_export_endpoint_override() -> None:
    settings = Settings(
        telemetry_backend="phoenix",
        telemetry_otlp_endpoint="http://collector:4318/v1/traces",
        telemetry_api_key="override-key",
    )
    endpoint, headers = resolve_otlp_export(settings)
    assert endpoint == "http://collector:4318/v1/traces"
    assert headers == {"Authorization": "Bearer override-key"}
