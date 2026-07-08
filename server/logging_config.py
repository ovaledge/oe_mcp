"""Stderr logging for stdio MCP (stdout is reserved for the MCP protocol)."""

import logging
import sys


def configure_stderr_logging(level: int = logging.INFO) -> None:
    """Attach a stderr handler to the root logger if none exist (idempotent)."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


def configure_runtime_observability(level: int = logging.INFO) -> None:
    """Bootstrap stderr logging and optional OTLP telemetry (idempotent)."""
    configure_stderr_logging(level=level)
    from server.telemetry import setup_telemetry

    setup_telemetry()
