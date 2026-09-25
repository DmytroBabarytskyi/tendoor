from datetime import timedelta

from tendoor.api.auth import REFRESH_COOKIE
from tendoor.infra.security import TokenService
from tests.fakes import PASSWORD


async def test_login_returns_access_token_and_httponly_refresh_cookie(client, fake):
    resp = await client.post("/api/auth/login", json={"email": "Analyst@Test.ua", "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "analyst"
    assert body["expires_in"] == 15 * 60
    cookie = resp.headers["set-cookie"]
    assert REFRESH_COOKIE in cookie and "HttpOnly" in cookie and "samesite=strict" in cookie.lower()
    assert "Path=/api/auth" in cookie
    assert fake.users.users[fake.analyst.id].last_login_at is not None
    assert fake.audit.entries[-1].action == "LOGIN"


async def test_wrong_password_is_rejected_and_audited(client, fake):
    resp = await client.post("/api/auth/login", json={"email": "analyst@test.ua", "password": "wrong-pass-1"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Невірний email або пароль"
    assert fake.audit.entries[-1].action == "LOGIN_FAILED"


async def test_unknown_email_gives_same_error(client):
    resp = await client.post("/api/auth/login", json={"email": "nobody@test.ua", "password": PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Невірний email або пароль"


async def test_inactive_user_cannot_login(client, fake):
    fake.users.add("blocked@test.ua", "auditor", active=False)
    resp = await client.post("/api/auth/login", json={"email": "blocked@test.ua", "password": PASSWORD})
    assert resp.status_code == 401


async def test_brute_force_is_rate_limited(client):
    bad = {"email": "admin@test.ua", "password": "wrong-pass-1"}
    for _ in range(5):
        assert (await client.post("/api/auth/login", json=bad)).status_code == 401
    resp = await client.post("/api/auth/login", json={"email": "admin@test.ua", "password": PASSWORD})
    assert resp.status_code == 429  # навіть правильний пароль після перевищення ліміту
    assert int(resp.headers["retry-after"]) > 0


async def test_refresh_rotates_session(client, login):
    await login("auditor@test.ua")
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "auditor@test.ua"


async def test_logout_revokes_access_and_refresh(client, login):
    headers = await login("auditor@test.ua")
    assert (await client.post("/api/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
    client.cookies.clear()
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_refresh_token_cannot_be_used_as_access(client, fake):
    refresh = fake.tokens.refresh_token(fake.admin.id, "admin", 0)
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


async def test_expired_and_forged_tokens_rejected(client, fake):
    expired = TokenService(
        "test-secret-test-secret-test-secret-42", timedelta(seconds=-1), timedelta(days=1)
    ).access_token(fake.admin.id, "admin", 0)
    forged = TokenService(
        "another-secret-another-secret-12345", timedelta(minutes=5), timedelta(days=1)
    ).access_token(fake.admin.id, "admin", 0)
    for token in (expired, forged, "not-a-jwt"):
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


async def test_change_password(client, login):
    headers = await login("auditor@test.ua")
    weak = {"old_password": PASSWORD, "new_password": "short"}
    assert (await client.post("/api/auth/change-password", json=weak, headers=headers)).status_code == 422
    wrong = {"old_password": "nope-nope-1", "new_password": "New-password-2"}
    assert (await client.post("/api/auth/change-password", json=wrong, headers=headers)).status_code == 400
    ok = {"old_password": PASSWORD, "new_password": "New-password-2"}
    resp = await client.post("/api/auth/change-password", json=ok, headers=headers)
    assert resp.status_code == 200
    # старий access-токен більше не діє, новий — діє
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
    new_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert (await client.get("/api/auth/me", headers=new_headers)).status_code == 200
    await login("auditor@test.ua", "New-password-2")
