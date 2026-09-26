"""Заявка на доступ (A4.1): подання без входу, розгляд лише адміністратором."""

import pytest

BODY = {
    "email": "new@test.ua",
    "full_name": "Нова Аудиторка",
    "role": "auditor",
    "password": "Long-password-1",
}


async def test_submit_without_login(client, fake):
    resp = await client.post("/api/auth/register", json=BODY)
    assert resp.status_code == 201 and resp.json()["status"] == "pending"
    assert (await client.post("/api/auth/register", json=BODY)).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "email": "not-an-email"},
        {**BODY, "role": "admin"},  # роль адміністратора заявкою не видається
        {**BODY, "full_name": "x"},
    ],
)
async def test_submit_validation(client, body):
    assert (await client.post("/api/auth/register", json=body)).status_code == 422


async def test_admin_reviews_requests(client, login, fake):
    await client.post("/api/auth/register", json=BODY)
    auditor = await login("auditor@test.ua")
    assert (await client.get("/api/registrations", headers=auditor)).status_code == 403
    admin = await login("admin@test.ua")
    assert (await client.get("/api/badges", headers=admin)).json()["registrations"] == 1
    pending = (await client.get("/api/registrations?status_=pending", headers=admin)).json()
    rid = pending[0]["id"]
    ok = await client.post(f"/api/registrations/{rid}/approve", json={"role": "analyst"}, headers=admin)
    assert ok.status_code == 200 and ok.json()["status"] == "approved" and ok.json()["role"] == "analyst"
    assert (
        await client.post("/api/registrations/999/reject", json={"reason": "невідомо хто"}, headers=admin)
    ).status_code == 404
    short = await client.post(f"/api/registrations/{rid}/reject", json={"reason": "x"}, headers=admin)
    assert short.status_code == 422
