"""Заявка на доступ на реальній БД: погодження створює користувача, який може увійти з паролем із заявки."""

import pytest
from sqlalchemy import delete, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.infra.security import hash_password, verify_password
from tendoor.repositories.sql.access import SqlUserRepository
from tendoor.repositories.sql.models import AppUser, AuditLog, RegistrationRequest
from tendoor.repositories.sql.registrations import SqlRegistrationRepository
from tendoor.services.registration import RegistrationError, RegistrationService

pytestmark = pytest.mark.integration
DOMAIN = "@reg.test.dev"


@pytest.fixture
async def ctx():
    d = Databases(Settings())
    try:
        async with d.session_factory() as s:
            await s.execute(text("SELECT 1 FROM registration_request LIMIT 1"))
    except Exception as exc:
        await d.close()
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    users = SqlUserRepository(d.session_factory)
    admin = await users.create(None, "admin" + DOMAIN, "Адмін", "admin", hash_password("Pass-word-123"))
    yield d, RegistrationService(SqlRegistrationRepository(d.session_factory), users), users, admin
    async with d.session_factory() as s, s.begin():
        await s.execute(delete(RegistrationRequest).where(RegistrationRequest.email.like(f"%{DOMAIN}")))
        await s.execute(
            text(
                "DELETE FROM audit_log WHERE entity = 'registration_request' OR user_id IN "
                "(SELECT id FROM app_user WHERE email LIKE :d)"
            ),
            {"d": f"%{DOMAIN}"},
        )
        await s.execute(delete(AuditLog).where(AuditLog.user_id == admin.id))
        await s.execute(delete(AppUser).where(AppUser.email.like(f"%{DOMAIN}")))
    await d.close()


async def test_approve_creates_user_with_requested_password(ctx):
    d, svc, users, admin = ctx
    r = await svc.submit(
        "Olena" + DOMAIN, "Олена Аудиторка", "auditor", "Strong-pass-2026", "відділ моніторингу"
    )
    assert r["status"] == "pending" and r["email"] == "olena" + DOMAIN
    with pytest.raises(RegistrationError, match="розглядається"):
        await svc.submit("olena" + DOMAIN, "Дубль", "auditor", "Strong-pass-2026", None)
    assert await svc.count_pending() >= 1

    done = await svc.approve(admin.id, r["id"], "analyst")
    assert done["status"] == "approved" and done["decided_by_name"] == "Адмін" and done["user_id"]
    found = await users.get_with_hash("olena" + DOMAIN)
    assert found and found[0].role == "analyst" and verify_password(found[1], "Strong-pass-2026")
    with pytest.raises(RegistrationError, match="вже розглянуто"):
        await svc.reject(admin.id, r["id"], "запізно")
    with pytest.raises(RegistrationError, match="уже існує"):
        await svc.submit("olena" + DOMAIN, "Ще раз", "auditor", "Strong-pass-2026", None)

    async with d.session_factory() as s:
        payloads = (
            (
                await s.execute(
                    text(
                        "SELECT payload::text FROM audit_log "
                        "WHERE entity = 'registration_request' AND entity_key = :k"
                    ),
                    {"k": str(r["id"])},
                )
            )
            .scalars()
            .all()
        )
    assert payloads and all("password_hash" not in p for p in payloads)  # хеш пароля в журнал не потрапляє


async def test_reject_requires_reason(ctx):
    _, svc, users, admin = ctx
    r = await svc.submit("petro" + DOMAIN, "Петро", "analyst", "Strong-pass-2026", None)
    with pytest.raises(RegistrationError, match="причину"):
        await svc.reject(admin.id, r["id"], "  ")
    done = await svc.reject(admin.id, r["id"], "невідома особа")
    assert done["status"] == "rejected" and done["reject_reason"] == "невідома особа"
    assert await users.get_with_hash("petro" + DOMAIN) is None
    assert await svc.approve(admin.id, 10**9, "auditor") is None
