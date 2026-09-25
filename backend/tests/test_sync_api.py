import pytest


@pytest.fixture
async def analyst(login):
    return await login("analyst@test.ua")


async def test_create_and_get_job(client, analyst, fake):
    body = {"date_from": "2026-09-01", "date_to": "2026-09-07", "cpv_prefixes": ["15", " 0322 "]}
    resp = await client.post("/api/sync/jobs", json=body, headers=analyst)
    assert resp.status_code == 201
    job = resp.json()
    assert job["status"] == "queued"
    assert job["cpv_prefixes"] == ["15", "0322"]
    assert job["categories"] == ["goods"]
    assert job["created_by"] == fake.analyst.id

    assert (await client.get(f"/api/sync/jobs/{job['id']}", headers=analyst)).json()["id"] == job["id"]
    assert len((await client.get("/api/sync/jobs", headers=analyst)).json()) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"date_from": "2026-09-10", "date_to": "2026-09-01"},  # переплутані межі
        {"date_from": "2026-01-01", "date_to": "2026-12-31"},  # задовгий період
        {"date_from": "2026-09-01", "date_to": "2026-09-02", "cpv_prefixes": ["15a"]},
        {"date_from": "2026-09-01", "date_to": "2026-09-02", "categories": ["food"]},
    ],
)
async def test_invalid_job_rejected(client, analyst, body):
    assert (await client.post("/api/sync/jobs", json=body, headers=analyst)).status_code == 422


async def test_unknown_job_404(client, analyst):
    assert (await client.get("/api/sync/jobs/999", headers=analyst)).status_code == 404


async def test_stats_available_to_auditor(client, login):
    stats = (await client.get("/api/procurement/stats", headers=await login("auditor@test.ua"))).json()
    assert stats["tenders"] == 3
    assert stats["raw_documents"] == 5
