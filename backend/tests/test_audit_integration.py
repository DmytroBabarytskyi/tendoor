"""Тригер trg_audit на реальному PostgreSQL: автор змін, лише змінені поля, без хешу пароля."""

import pytest
from sqlalchemy import delete, select, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.infra.security import hash_password
from tendoor.repositories.sql.access import SqlConfigRepository, SqlUserRepository
from tendoor.repositories.sql.models import AppUser, AuditLog

pytestmark = pytest.mark.integration

EMAILS = ("audit-actor@test.local", "audit-target@test.local")


@pytest.fixture
async def dbs():
    d = Databases(Settings())
    try:
        async with d.session_factory() as s:
            await s.execute(text("SELECT 1 FROM audit_log LIMIT 1"))
    except Exception as exc:
        await d.close()
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    yield d
    async with d.session_factory() as s, s.begin():
        ids = (await s.execute(select(AppUser.id).where(AppUser.email.in_(EMAILS)))).scalars().all()
        await s.execute(delete(AuditLog).where(AuditLog.user_id.in_(ids)))
        await s.execute(
            delete(AuditLog).where(
                AuditLog.entity == "app_user", AuditLog.entity_key.in_([str(i) for i in ids])
            )
        )
        await s.execute(delete(AppUser).where(AppUser.id.in_(ids)))
    await d.close()


async def _audit_rows(d: Databases, entity: str, key: str) -> list[AuditLog]:
    async with d.session_factory() as s:
        return list(
            (
                await s.execute(
                    select(AuditLog)
                    .where(AuditLog.entity == entity, AuditLog.entity_key == key)
                    .order_by(AuditLog.id)
                )
            ).scalars()
        )


async def test_audit_trigger_records_actor_and_diff(dbs):
    users = SqlUserRepository(dbs.session_factory)
    actor = await users.create(None, EMAILS[0], "Адмін Тестовий", "admin", hash_password("Pass-word-123"))
    target = await users.create(
        actor.id, EMAILS[1], "Аудитор Тестовий", "auditor", hash_password("Pass-word-123")
    )

    await users.update(actor.id, target.id, full_name="Аудитор Перейменований", role="analyst")
    await users.update(actor.id, target.id, password_hash=hash_password("Other-pass-456"))
    await users.touch_login(target.id)  # службове оновлення не має потрапляти в журнал

    rows = await _audit_rows(dbs, "app_user", str(target.id))
    assert [r.action for r in rows] == ["INSERT", "UPDATE", "UPDATE"]
    assert all(r.user_id == actor.id for r in rows)
    assert "password_hash" not in rows[0].payload and rows[0].payload["email"] == EMAILS[1]
    assert rows[1].payload["full_name"] == {"old": "Аудитор Тестовий", "new": "Аудитор Перейменований"}
    assert rows[1].payload["role_id"]["new"] == 2
    assert rows[2].payload == {"password": "changed"}


async def test_config_change_is_audited_with_key(dbs):
    users = SqlUserRepository(dbs.session_factory)
    actor = await users.create(None, EMAILS[0], "Адмін Тестовий", "admin", hash_password("Pass-word-123"))
    cfg = SqlConfigRepository(dbs.session_factory)
    before = (await cfg.get("homogeneity.thresholds"))["value"]
    try:
        await cfg.set(actor.id, "homogeneity.thresholds", {"good": 0.8, "warn": 0.5})
        rows = await _audit_rows(dbs, "pipeline_config", "homogeneity.thresholds")
        assert rows[-1].user_id == actor.id
        assert rows[-1].payload["value"] == {"old": before, "new": {"good": 0.8, "warn": 0.5}}
    finally:
        await cfg.set(actor.id, "homogeneity.thresholds", before)
        async with dbs.session_factory() as s, s.begin():
            await s.execute(
                delete(AuditLog).where(AuditLog.entity == "pipeline_config", AuditLog.user_id == actor.id)
            )
