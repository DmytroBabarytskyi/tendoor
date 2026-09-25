"""Тригери вердиктів на реальному PostgreSQL: історія змін і журнал аудиту з автором."""

import pytest
from sqlalchemy import delete, select, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.infra.security import hash_password
from tendoor.repositories.sql.access import SqlUserRepository
from tendoor.repositories.sql.models import AppUser, AuditLog, Verdict
from tendoor.repositories.sql.verdicts import SqlVerdictRepository

pytestmark = pytest.mark.integration
EMAIL = "verdict-auditor@test.dev"


@pytest.fixture
async def ctx():
    d = Databases(Settings())
    try:
        async with d.session_factory() as s:
            await s.execute(text("SELECT 1 FROM verdict_history LIMIT 1"))
            # позиція без вердикту — тест не змінює реальну розмітку
            item_id = (
                await s.execute(
                    text(
                        "SELECT min(i.id) FROM item i "
                        "LEFT JOIN verdict v ON v.item_id = i.id WHERE v.id IS NULL"
                    )
                )
            ).scalar()
    except Exception as exc:
        await d.close()
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    if item_id is None:
        await d.close()
        pytest.skip("немає позиції без вердикту")
    user = await SqlUserRepository(d.session_factory).create(
        None, EMAIL, "Тест Аудитор", "auditor", hash_password("Pass-word-123")
    )
    yield d, item_id, user
    async with d.session_factory() as s, s.begin():
        await s.execute(
            text(
                "DELETE FROM audit_log WHERE entity = 'verdict' AND entity_key IN "
                "(SELECT id::text FROM verdict WHERE item_id = :item)"
            ),
            {"item": item_id},
        )
        await s.execute(delete(Verdict).where(Verdict.item_id == item_id))
        await s.execute(delete(AuditLog).where(AuditLog.user_id == user.id))
        await s.execute(delete(AppUser).where(AppUser.id == user.id))
    await d.close()


async def test_history_and_audit(ctx):
    d, item_id, user = ctx
    repo = SqlVerdictRepository(d.session_factory)
    v1 = await repo.upsert(user.id, item_id, None, "needs_review", "other", "перевірити договір")
    v2 = await repo.upsert(user.id, item_id, None, "confirmed", "unit_error", "ціна за упаковку, а не за кг")
    await repo.upsert(
        user.id, item_id, None, "confirmed", "unit_error", "ціна за упаковку, а не за кг"
    )  # без змін
    assert v1["id"] == v2["id"] and v2["user_email"] == EMAIL

    history = await repo.history(item_id)
    assert [(h["old_status"], h["new_status"]) for h in history] == [
        ("needs_review", "confirmed"),
        (None, "needs_review"),
    ]
    assert history[0]["new_reason"] == "unit_error" and history[0]["user_email"] == EMAIL

    async with d.session_factory() as s:
        audit = await s.execute(
            select(AuditLog.action)
            .where(AuditLog.entity == "verdict", AuditLog.entity_key == str(v1["id"]))
            .order_by(AuditLog.id)
        )
        assert list(audit.scalars()) == ["INSERT", "UPDATE"]
