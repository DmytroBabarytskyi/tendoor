"""Тригери вердиктів на реальному PostgreSQL: історія змін і журнал аудиту з автором."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.infra.security import hash_password
from tendoor.repositories.sql.access import SqlUserRepository
from tendoor.repositories.sql.models import AppUser, AuditLog, Item, ProcuringEntity, Tender, Verdict
from tendoor.repositories.sql.procurement import SqlProcurementRepository
from tendoor.repositories.sql.verdicts import SqlVerdictRepository
from tendoor.services.normalization import EntityRec, ItemRec, NormalizedTender, cpv_chain
from tendoor.services.review import ReviewError

pytestmark = pytest.mark.integration
EMAIL = "verdict-auditor@test.dev"
REVIEWER = "verdict-reviewer@test.dev"
TENDER = "test-verdict-1"
EDRPOU = "TEST-VERDICT"


def _tender() -> NormalizedTender:
    when = datetime(2020, 2, 1, tzinfo=UTC)
    item = ItemRec(
        prozorro_item_id="1",
        prozorro_lot_id=None,
        prozorro_contract_id=None,
        cpv_code="15311100",
        unit_code="KGM",
        unit_name="кілограм",
        description="Картопля",
        description_clean="картопля",
        quantity=Decimal(100),
        unit_price=Decimal("18.50"),
        price_source="unit_value",
        vat_included=False,
    )
    return NormalizedTender(
        prozorro_id=TENDER,
        tender_code="UA-TEST-VERDICT",
        title="Тест",
        method_type="reporting",
        category="goods",
        status="complete",
        date_published=when,
        date_modified=when,
        value_amount=None,
        currency="UAH",
        vat_included=False,
        entity=EntityRec(EDRPOU, "Тестовий замовник"),
        items=[item],
        cpvs={c.code: c for c in cpv_chain("15311100", "Картопля")},
    )


@pytest.fixture
async def ctx():
    d = Databases(Settings())
    try:
        async with d.session_factory() as s:
            await s.execute(text("SELECT 1 FROM verdict_history LIMIT 1"))
    except Exception as exc:
        await d.close()
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    # власна тестова позиція — тест не змінює реальну розмітку
    await SqlProcurementRepository(d.session_factory).save_tenders([_tender()])
    async with d.session_factory() as s:
        item_id = (
            await s.execute(
                select(Item.id).join(Tender, Tender.id == Item.tender_id).where(Tender.prozorro_id == TENDER)
            )
        ).scalar_one()
    users = SqlUserRepository(d.session_factory)
    user = await users.create(None, EMAIL, "Тест Аудитор", "auditor", hash_password("Pass-word-123"))
    reviewer = await users.create(
        None, REVIEWER, "Тест Погоджувач", "auditor", hash_password("Pass-word-123")
    )
    yield d, item_id, user, reviewer
    async with d.session_factory() as s, s.begin():
        await s.execute(
            text(
                "DELETE FROM audit_log WHERE entity = 'verdict' AND entity_key IN "
                "(SELECT id::text FROM verdict WHERE item_id = :item)"
            ),
            {"item": item_id},
        )
        await s.execute(delete(Verdict).where(Verdict.item_id == item_id))
        await s.execute(delete(Tender).where(Tender.prozorro_id == TENDER))
        await s.execute(delete(ProcuringEntity).where(ProcuringEntity.edrpou == EDRPOU))
        await s.execute(delete(AuditLog).where(AuditLog.user_id.in_([user.id, reviewer.id])))
        await s.execute(delete(AppUser).where(AppUser.id.in_([user.id, reviewer.id])))
    await d.close()


async def test_review_cycle_history_and_audit(ctx):
    d, item_id, user, reviewer = ctx
    repo = SqlVerdictRepository(d.session_factory)
    v = await repo.apply(user.id, item_id, None, "take")
    assert v["state"] == "in_progress" and v["status"] is None and v["user_email"] == EMAIL
    with pytest.raises(ReviewError, match="в іншого"):
        await repo.apply(reviewer.id, item_id, None, "take")
    first = {"status": "needs_review", "reason": "other", "comment": "договір?"}
    await repo.apply(user.id, item_id, None, "submit", first)
    with pytest.raises(ReviewError, match="чотирьох очей"):
        await repo.apply(user.id, item_id, None, "approve")
    await repo.apply(reviewer.id, item_id, None, "return", {"comment": "уточніть одиницю виміру"})
    fixed = {"status": "confirmed", "reason": "unit_error", "comment": "ціна за упаковку"}
    await repo.apply(user.id, item_id, None, "submit", fixed)
    done = await repo.apply(reviewer.id, item_id, None, "approve", {"comment": None})
    assert done["state"] == "approved" and done["reviewer_name"] == "Тест Погоджувач" and done["reviewed_at"]

    history = await repo.history(item_id)
    assert [(h["old_state"], h["new_state"]) for h in reversed(history)] == [
        (None, "in_progress"),
        ("in_progress", "submitted"),
        ("submitted", "returned"),
        ("returned", "submitted"),
        ("submitted", "approved"),
    ]
    returned = next(h for h in history if h["new_state"] == "returned")
    assert returned["comment"] == "уточніть одиницю виміру" and returned["user_email"] == REVIEWER
    assert {"item_id": item_id, "status": "confirmed", "reason": "unit_error"} in await repo.labels()

    async with d.session_factory() as s:
        audit = await s.execute(
            select(AuditLog.action, AuditLog.user_id)
            .where(AuditLog.entity == "verdict", AuditLog.entity_key == str(v["id"]))
            .order_by(AuditLog.id)
        )
        rows = audit.all()
        assert [a for a, _ in rows] == ["INSERT"] + ["UPDATE"] * 4
        assert rows[-1][1] == reviewer.id  # автор зміни — погоджувач


async def test_four_eyes_is_enforced_by_database(ctx):
    d, item_id, user, _ = ctx
    await SqlVerdictRepository(d.session_factory).apply(
        user.id, item_id, None, "submit", {"status": "confirmed", "reason": "overpriced"}
    )
    with pytest.raises(IntegrityError, match="four_eyes"):
        async with d.session_factory() as s, s.begin():
            await s.execute(
                text("UPDATE verdict SET state = 'approved', reviewer_id = user_id WHERE item_id = :i"),
                {"i": item_id},
            )
