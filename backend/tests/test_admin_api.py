import pytest

SYNC_BODY = {"date_from": "2026-09-01", "date_to": "2026-09-01"}


@pytest.mark.parametrize(
    ("method", "url", "body", "allowed"),
    [
        ("post", "/api/sync/jobs", SYNC_BODY, {"admin", "analyst"}),
        ("get", "/api/sync/jobs", None, {"admin", "analyst"}),
        ("get", "/api/procurement/stats", None, {"admin", "analyst", "auditor"}),
        ("get", "/api/users", None, {"admin"}),
        ("get", "/api/audit-log", None, {"admin"}),
        ("get", "/api/settings", None, {"admin", "analyst", "auditor"}),
        ("put", "/api/settings/detection.defaults", {"value": {"k_max": 10}}, {"admin"}),
    ],
)
async def test_role_matrix(client, login, method, url, body, allowed):
    """Матриця доступу ролей до функцій (A4.2): без токена — 401, чужа роль — 403."""
    assert (await client.request(method, url, json=body)).status_code == 401
    for role in ("admin", "analyst", "auditor"):
        headers = await login(f"{role}@test.ua")
        resp = await client.request(method, url, json=body, headers=headers)
        assert (resp.status_code < 400) == (role in allowed), (role, resp.status_code, resp.text)
        if role not in allowed:
            assert resp.status_code == 403


@pytest.fixture
async def admin(login):
    return await login("admin@test.ua")


async def test_create_user_validation(client, admin):
    base = {"email": "new@test.ua", "full_name": "Новий Аудитор", "role": "auditor"}
    assert (
        await client.post("/api/users", json=base | {"password": "123"}, headers=admin)
    ).status_code == 400
    assert (
        await client.post(
            "/api/users", json=base | {"password": "Good-pass-123", "role": "boss"}, headers=admin
        )
    ).status_code == 400
    resp = await client.post("/api/users", json=base | {"password": "Good-pass-123"}, headers=admin)
    assert resp.status_code == 201
    assert resp.json()["role"] == "auditor"
    dup = await client.post("/api/users", json=base | {"password": "Good-pass-123"}, headers=admin)
    assert dup.status_code == 409


async def test_admin_cannot_lock_or_demote_self(client, admin, fake):
    uid = fake.admin.id
    assert (
        await client.patch(f"/api/users/{uid}", json={"is_active": False}, headers=admin)
    ).status_code == 400
    assert (
        await client.patch(f"/api/users/{uid}", json={"role": "auditor"}, headers=admin)
    ).status_code == 400


async def test_admin_can_manage_other_admins_but_always_one_remains(client, admin, fake, login):
    second = fake.users.add("admin2@test.ua", "admin")
    resp = await client.patch(f"/api/users/{second.id}", json={"role": "analyst"}, headers=admin)
    assert resp.status_code == 200 and resp.json()["role"] == "analyst"
    # пониження колеги не зачіпає діючого адміністратора
    assert (await client.get("/api/auth/me", headers=admin)).json()["role"] == "admin"


async def test_blocking_user_ends_sessions(client, admin, login, fake):
    auditor = await login("auditor@test.ua")
    resp = await client.patch(f"/api/users/{fake.auditor.id}", json={"is_active": False}, headers=admin)
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    assert (await client.get("/api/auth/me", headers=auditor)).status_code == 401


async def test_settings_update_and_audit_log(client, admin, fake):
    resp = await client.put("/api/settings/detection.defaults", json={"value": {"k_max": 12}}, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["value"] == {"k_max": 12} and resp.json()["updated_by"] == fake.admin.id
    assert (await client.put("/api/settings/nope", json={"value": {}}, headers=admin)).status_code == 404

    page = (await client.get("/api/audit-log?action=LOGIN", headers=admin)).json()
    assert page["total"] >= 1 and all(e["action"] == "LOGIN" for e in page["items"])
