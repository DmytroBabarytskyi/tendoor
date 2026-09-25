"""Інтеграційні тести з реальним PostgreSQL (docker compose up -d postgres).

Пропускаються, якщо база недоступна. Перевіряють тригер trg_item_normalize та upsert.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.repositories.sql.models import Item, ProcuringEntity, Tender, Unit
from tendoor.repositories.sql.procurement import SqlProcurementRepository
from tendoor.services.normalization import EntityRec, ItemRec, NormalizedTender, cpv_chain

pytestmark = pytest.mark.integration

TEST_ID = "test0000000000000000000000000001"
TEST_EDRPOU = "TEST-00000000"


@pytest.fixture
async def dbs():
    d = Databases(Settings())
    try:
        await d.ping_postgres()
        await d.engine.dispose()
        async with d.session_factory() as s:
            await s.execute(text("SELECT 1 FROM item LIMIT 1"))
    except Exception as exc:
        await d.close()
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    yield d
    async with d.session_factory() as s, s.begin():
        await s.execute(delete(Tender).where(Tender.prozorro_id == TEST_ID))
        await s.execute(delete(ProcuringEntity).where(ProcuringEntity.edrpou == TEST_EDRPOU))
        await s.execute(delete(Unit).where(Unit.code == "XTEST"))
    await d.close()


def _item(item_id: str, unit: str, qty: str, price: str) -> ItemRec:
    return ItemRec(
        prozorro_item_id=item_id,
        prozorro_lot_id=None,
        prozorro_contract_id=None,
        cpv_code="15311100",
        unit_code=unit,
        unit_name="тестова одиниця",
        description="Картопля",
        description_clean="картопля",
        quantity=Decimal(qty),
        unit_price=Decimal(price),
        price_source="unit_value",
        vat_included=False,
    )


def _tender(items: list[ItemRec]) -> NormalizedTender:
    now = datetime.now(UTC)
    return NormalizedTender(
        prozorro_id=TEST_ID,
        tender_code="UA-TEST",
        title="Тест",
        method_type="reporting",
        category="goods",
        status="complete",
        date_published=now,
        date_modified=now,
        value_amount=Decimal("100"),
        currency="UAH",
        vat_included=False,
        entity=EntityRec(TEST_EDRPOU, "Тестовий замовник"),
        items=items,
        cpvs={c.code: c for c in cpv_chain("15311100", "Картопля")},
    )


async def test_trigger_converts_to_base_unit_and_upsert_removes_stale(dbs):
    repo = SqlProcurementRepository(dbs.session_factory)
    await repo.save_tenders(
        [
            _tender(
                [
                    _item("g", "GRM", "500", "0.05"),  # 500 г по 0,05 грн/г
                    _item("t", "TNE", "2", "18000"),  # 2 т по 18 000 грн/т
                    _item("x", "XTEST", "3", "7"),  # невідома одиниця додається автоматично
                ]
            )
        ]
    )

    async with dbs.session_factory() as s:
        rows = {
            r.prozorro_item_id: r
            for r in (
                await s.execute(select(Item).join(Tender).where(Tender.prozorro_id == TEST_ID))
            ).scalars()
        }
    assert rows["g"].base_unit_code == "KGM"
    assert rows["g"].quantity_base == Decimal("0.5")
    assert rows["g"].unit_price_base == Decimal("50")
    assert (rows["t"].quantity_base, rows["t"].unit_price_base) == (Decimal("2000"), Decimal("18"))
    assert (rows["x"].base_unit_code, rows["x"].unit_price_base) == ("XTEST", Decimal("7"))

    # повторне збереження без позиції «x» видаляє її, а «g» оновлюється на місці
    await repo.save_tenders([_tender([_item("g", "GRM", "1000", "0.04"), _item("t", "TNE", "2", "18000")])])
    async with dbs.session_factory() as s:
        rows2 = {
            r.prozorro_item_id: r
            for r in (
                await s.execute(select(Item).join(Tender).where(Tender.prozorro_id == TEST_ID))
            ).scalars()
        }
    assert set(rows2) == {"g", "t"}
    assert rows2["g"].id == rows["g"].id
    assert rows2["g"].unit_price_base == Decimal("40")
