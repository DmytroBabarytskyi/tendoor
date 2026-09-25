import pytest
from httpx import ASGITransport, AsyncClient

from tendoor.api.app import create_app
from tests.fakes import FakeContainer


@pytest.fixture
async def client():
    app = create_app(container=FakeContainer(), probes={})
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c,
    ):
        yield c


async def test_create_and_get_job(client):
    body = {"date_from": "2026-09-01", "date_to": "2026-09-07", "cpv_prefixes": ["15", " 0322 "]}
    resp = await client.post("/api/sync/jobs", json=body)
    assert resp.status_code == 201
    job = resp.json()
    assert job["status"] == "queued"
    assert job["cpv_prefixes"] == ["15", "0322"]
    assert job["categories"] == ["goods"]

    assert (await client.get(f"/api/sync/jobs/{job['id']}")).json()["id"] == job["id"]
    assert len((await client.get("/api/sync/jobs")).json()) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"date_from": "2026-09-10", "date_to": "2026-09-01"},  # переплутані межі
        {"date_from": "2026-01-01", "date_to": "2026-12-31"},  # задовгий період
        {"date_from": "2026-09-01", "date_to": "2026-09-02", "cpv_prefixes": ["15a"]},
        {"date_from": "2026-09-01", "date_to": "2026-09-02", "categories": ["food"]},
    ],
)
async def test_invalid_job_rejected(client, body):
    assert (await client.post("/api/sync/jobs", json=body)).status_code == 422


async def test_unknown_job_404(client):
    assert (await client.get("/api/sync/jobs/999")).status_code == 404


async def test_stats(client):
    stats = (await client.get("/api/procurement/stats")).json()
    assert stats["tenders"] == 3
    assert stats["raw_documents"] == 5
