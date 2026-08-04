from __future__ import annotations

from pathlib import Path

from server.config import Settings, version_from_pyproject


def test_version_from_pyproject_reads_poetry_version() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert version_from_pyproject(repo_root) == "1.0.4"


def test_version_from_pyproject_missing_file() -> None:
    assert version_from_pyproject(Path("/nonexistent")) is None


def test_settings_mcp_server_version_prefers_explicit_env(monkeypatch) -> None:
    monkeypatch.setenv("MCP_SERVER_VERSION", "9.9.9")
    s = Settings()
    assert s.mcp_server_version == "9.9.9"


def test_settings_mcp_server_version_resolves_from_pyproject_when_unset(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MCP_SERVER_VERSION", raising=False)
    s = Settings(mcp_server_version="")
    assert s.mcp_server_version == "1.0.4"
