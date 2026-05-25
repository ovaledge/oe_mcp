"""Stdio entrypoint (entrypoints/local.py)."""

from unittest.mock import AsyncMock, patch

from server.auth.context import current_oe_jwt


class TestLocalEntrypoint:
    async def test_local_lifespan_sets_oe_jwt(self) -> None:
        with patch(
            "entrypoints.local.get_or_refresh_local_token",
            new=AsyncMock(return_value="local-oe-jwt"),
        ):
            from entrypoints.local import local_lifespan

            async with local_lifespan(None):
                assert current_oe_jwt.get() == "local-oe-jwt"

    def test_main_runs_stdio_transport(self) -> None:
        with (
            patch("entrypoints.local.configure_stderr_logging") as log_cfg,
            patch("entrypoints.local.mcp.run") as run,
        ):
            from entrypoints.local import main

            main()
        log_cfg.assert_called_once()
        run.assert_called_once_with(transport="stdio")
