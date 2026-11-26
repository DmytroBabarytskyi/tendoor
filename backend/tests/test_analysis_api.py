import pytest

from tendoor.ml.calibration import load_calibrator

BODY = {"cpv_prefixes": ["1531"], "date_from": "2026-09-01", "date_to": "2026-09-30"}


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "cpv_prefixes": []},
        {**BODY, "cpv_prefixes": ["x15"]},
        {**BODY, "date_from": "2026-10-01"},
        {**BODY, "date_from": "2024-01-01"},  # довше за рік
    ],
)
async def test_selection_validation(client, login, body):
    headers = await login("auditor@test.ua")
    assert (await client.post("/api/analysis/preview", json=body, headers=headers)).status_code == 422


async def test_full_cpv_code_is_normalised_to_prefix(client, login, fake):
    headers = await login("auditor@test.ua")
    resp = await client.post(
        "/api/analysis/requests", json={**BODY, "cpv_prefixes": ["15310000", "1531"]}, headers=headers
    )
    assert resp.status_code == 201
    assert fake.detection.submitted[-1][1].cpv_prefixes == ("1531",)


async def test_auditor_cannot_override_model_params(client, login):
    headers = await login("auditor@test.ua")
    resp = await client.post(
        "/api/analysis/requests", json={**BODY, "params": {"z_strong": 5.0}}, headers=headers
    )
    assert resp.status_code == 403


async def test_analyst_can_override_model_params(client, login, fake):
    headers = await login("analyst@test.ua")
    resp = await client.post(
        "/api/analysis/requests", json={**BODY, "params": {"z_strong": 5.0}}, headers=headers
    )
    assert resp.status_code == 201
    assert fake.detection.submitted[-1][2] == {"z_strong": 5.0}


async def test_auditors_see_only_own_requests(client, login, fake):
    other = fake.analysis.add(fake.analyst.id)
    mine = fake.analysis.add(fake.auditor.id)
    headers = await login("auditor@test.ua")
    assert (await client.get(f"/api/analysis/requests/{other['id']}", headers=headers)).status_code == 404
    assert (await client.get(f"/api/analysis/requests/{mine['id']}", headers=headers)).status_code == 200
    ids = [r["id"] for r in (await client.get("/api/analysis/requests", headers=headers)).json()]
    assert ids == [mine["id"]]
    analyst = await login("analyst@test.ua")
    assert (await client.get(f"/api/analysis/requests/{mine['id']}", headers=analyst)).status_code == 200


async def test_results_require_finished_request(client, login, fake):
    pending = fake.analysis.add(fake.auditor.id, status="running")
    done = fake.analysis.add(fake.auditor.id)
    headers = await login("auditor@test.ua")
    url = "/api/analysis/requests/{}/anomalies"
    assert (await client.get(url.format(pending["id"]), headers=headers)).status_code == 409
    body = (await client.get(url.format(done["id"]), headers=headers)).json()
    assert body["total"] == 1
    explanation = body["items"][0]["explanation"]
    assert "у 4,0 раза вища за медіану групи (20,00 грн/KGM)" in explanation
    # аудитору показуються лише ознаки, що впливають на рішення v2: сильне відхилення так, DBSCAN — ні
    assert "відхилення в 4,2 раза більше за звичайний розкид" in explanation and "DBSCAN" not in explanation


async def test_analysis_requires_authentication(client):
    assert (await client.post("/api/analysis/preview", json=BODY)).status_code == 401


async def test_params_endpoint_is_for_analysts(client, login):
    auditor = await login("auditor@test.ua")
    assert (await client.get("/api/analysis/params", headers=auditor)).status_code == 403
    analyst = await login("analyst@test.ua")
    body = (await client.get("/api/analysis/params", headers=analyst)).json()
    assert body["defaults"]["z_strong"] == 4.0
    assert body["bounds"]["anomaly_threshold"] == [0.05, 0.95]
    assert body["calibrator_threshold"] == pytest.approx(load_calibrator().meta["threshold"])
