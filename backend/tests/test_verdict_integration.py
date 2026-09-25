"""Тригери вердиктів на реальному PostgreSQL: історія змін і журнал аудиту з автором."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.infra.security import hash_password
from tendoor.repositories.sql.access import SqlUserRepository
from tendoor.repositories.sql.models import AppUser, AuditLog, Item, ProcuringEntity, Tender, Verdict
from tendoor.repositories.sql.procurement import SqlProcurementRepository
from tendoor.repositories.sql.verdicts import SqlVerdictRepository
from tendoor.services.normalization import EntityRec, ItemRec, NormalizedTender, cpv_chain

pytestmark = pytest.mark.integration
EMAIL = "verdict-auditor@test.dev"
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
        await s.execute(delete(Tender).where(Tender.prozorro_id == TENDER))
        await s.execute(delete(ProcuringEntity).where(ProcuringEntity.edrpou == EDRPOU))
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
