"""``POST /mcp`` must not 307 to ``/mcp/`` before MCP clients see the response."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.asgi_normalize_mcp_path import NormalizeMcpMountSlashMiddleware


def test_post_slashless_mcp_hits_slash_route_without_redirect() -> None:
    app = FastAPI()

    @app.post("/mcp/")
    async def mcp_root() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(NormalizeMcpMountSlashMiddleware)

    with TestClient(app) as client:
        r = client.post("/mcp", follow_redirects=False)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
