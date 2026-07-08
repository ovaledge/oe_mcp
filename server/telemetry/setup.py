"""Configure OTLP trace export to Phoenix or Langfuse."""

from __future__ import annotations

import atexit
import base64
import logging
import os
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

from server.config import Settings, get_settings

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import SpanProcessor

logger = logging.getLogger(__name__)

_telemetry_configured = False
_telemetry_enabled = False


def resolve_otlp_export(settings: Settings) -> tuple[str, dict[str, str]] | None:
    """Return OTLP HTTP traces endpoint and headers for the configured backend."""
    backend = settings.telemetry_backend
    if backend == "none":
        return None

    override = settings.telemetry_otlp_endpoint.strip()
    if override:
        return override, _optional_bearer_header(settings.telemetry_api_key)

    if backend == "phoenix":
        host = settings.phoenix_host.rstrip("/")
        headers = _optional_bearer_header(settings.phoenix_api_key)
        project = (
            settings.telemetry_project_name.strip() or settings.telemetry_service_name.strip()
        )
        if project:
            headers["x-project-name"] = project
        return f"{host}/v1/traces", headers

    if backend == "langfuse":
        host = settings.langfuse_host.rstrip("/")
        public_key = settings.langfuse_public_key.strip()
        secret_key = settings.langfuse_secret_key.strip()
        if not public_key or not secret_key:
            raise ValueError(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required when "
                "TELEMETRY_BACKEND=langfuse"
            )
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode("ascii")
        return f"{host}/api/public/otel/v1/traces", {"Authorization": f"Basic {token}"}

    raise ValueError(f"Unsupported TELEMETRY_BACKEND: {backend!r}")


def _running_on_aws_lambda() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _span_processor(exporter: OTLPSpanExporter) -> SpanProcessor:
    # Lambda freezes right after the response; export each span immediately.
    if _running_on_aws_lambda():
        return SimpleSpanProcessor(exporter)
    return BatchSpanProcessor(exporter)


def _optional_bearer_header(api_key: str) -> dict[str, str]:
    key = api_key.strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def setup_telemetry(*, settings: Settings | None = None) -> bool:
    """
    Configure process-wide OTLP export when ``telemetry_backend`` is set.

    Returns True when a tracer provider was installed, False when telemetry is disabled.
    Idempotent: subsequent calls are no-ops.
    """
    global _telemetry_configured, _telemetry_enabled
    if _telemetry_configured:
        return _telemetry_enabled

    cfg = settings or get_settings()
    export = resolve_otlp_export(cfg)
    if export is None:
        logger.debug("telemetry disabled (TELEMETRY_BACKEND=none)")
        _telemetry_configured = True
        _telemetry_enabled = False
        return False

    endpoint, headers = export
    resource = Resource.create(
        {
            "service.name": cfg.telemetry_service_name,
            "service.version": cfg.mcp_server_version,
            "openinference.project.name": (
                cfg.telemetry_project_name.strip() or cfg.telemetry_service_name
            ),
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
    processor = _span_processor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    atexit.register(shutdown_telemetry)
    _telemetry_configured = True
    _telemetry_enabled = True
    logger.info(
        "telemetry enabled backend=%s endpoint=%s service=%s",
        cfg.telemetry_backend,
        endpoint,
        cfg.telemetry_service_name,
    )
    return True


def flush_telemetry(*, timeout_millis: int = 5000) -> None:
    """Force-export buffered spans (no-op when telemetry is disabled)."""
    if not _telemetry_enabled:
        return
    provider = trace.get_tracer_provider()
    force_flush = getattr(provider, "force_flush", None)
    if callable(force_flush):
        force_flush(timeout_millis=timeout_millis)


def shutdown_telemetry() -> None:
    """Flush and shut down the tracer provider (safe to call multiple times)."""
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
