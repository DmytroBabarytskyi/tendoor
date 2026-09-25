from httpx import ASGITransport, AsyncClient

from tendoor.api.app import create_app
from tests.fakes import FakeContainer


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise ConnectionError("down")


async def _get_health(probes):
    app = create_app(container=FakeContainer(), probes=probes)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        return await client.get("/api/health")


async def test_health_ok_when_all_storages_available():
    resp = await _get_health({"postgres": _ok, "mongo": _ok})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"postgres": "ok", "mongo": "ok"}


async def test_health_degraded_when_storage_down():
    resp = await _get_health({"postgres": _ok, "mongo": _fail})
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["mongo"] == "error: ConnectionError"
