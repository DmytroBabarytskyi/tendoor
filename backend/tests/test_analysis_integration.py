"""Повний цикл A2 на реальному PostgreSQL: запит → навчання (як у worker) → результати → кеш."""

from datetime import UTC, date, datetime
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import any_, delete, select, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.repositories.sql.access import SqlConfigRepository
from tendoor.repositories.sql.analysis import AnalysisFilters, SqlAnalysisRepository
from tendoor.repositories.sql.models import AnalysisRequest, ModelRun, ProcuringEntity, Tender, Verdict
from tendoor.repositories.sql.procurement import SqlProcurementRepository
from tendoor.repositories.sql.verdicts import SqlVerdictRepository
from tendoor.services.detection import DetectionService
from tendoor.services.normalization import EntityRec, ItemRec, NormalizedTender, cpv_chain

pytestmark = pytest.mark.integration

TEST_CPV = "99999999"  # неіснуючий код — не перетинається з реальними даними
EDRPOU = "TEST-ANALYSIS"
DAY = date(2020, 1, 15)


@pytest.fixture
async def dbs():
    d = Databases(Settings())
    try:
        async with d.session_factory() as s:
            await s.execute(text("SELECT 1 FROM v_anomaly_queue LIMIT 1"))
    except Exception as exc:
        await d.close()
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    yield d
    async with d.session_factory() as s, s.begin():
        keys = select(AnalysisRequest.cache_key).where(any_(AnalysisRequest.cpv_prefixes) == TEST_CPV)
        await s.execute(delete(ModelRun).where(ModelRun.cache_key.in_(keys)))
        await s.execute(delete(AnalysisRequest).where(any_(AnalysisRequest.cpv_prefixes) == TEST_CPV))
        await s.execute(delete(Tender).where(Tender.prozorro_id.like("test-analysis-%")))
        await s.execute(delete(ProcuringEntity).where(ProcuringEntity.edrpou == EDRPOU))
        await s.execute(text("DELETE FROM cpv WHERE code LIKE '99%'"))  # тестовий код і його предки
    await d.close()


def _tender(i: int, price: float) -> NormalizedTender:
    when = datetime(2020, 1, 15, 10, tzinfo=UTC)
    item = ItemRec(
        prozorro_item_id="1",
        prozorro_lot_id=None,
        prozorro_contract_id=None,
        cpv_code=TEST_CPV,
        unit_code="KGM",
        unit_name="кілограм",
        description="Тестовий товар",
        description_clean="тестовий товар",
        quantity=Decimal(100 + i),
        unit_price=Decimal(str(round(price, 2))),
        price_source="unit_value",
        vat_included=False,
    )
    return NormalizedTender(
        prozorro_id=f"test-analysis-{i}",
        tender_code=f"UA-TEST-{i}",
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
        cpvs={c.code: c for c in cpv_chain(TEST_CPV, "Тестова категорія")},
    )


async def _run_cycle(dbs):
    """Дані → запит → навчання, як у worker. Повертає (repo, svc, filters, request)."""
    rng = np.random.default_rng(0)
    prices = list(50 * np.exp(rng.normal(0, 0.1, 40))) + [500.0]  # остання позиція в ~10 разів дорожча
    await SqlProcurementRepository(dbs.session_factory).save_tenders(
        [_tender(i, p) for i, p in enumerate(prices)]
    )

    repo = SqlAnalysisRepository(dbs.session_factory)
    svc = DetectionService(repo, SqlConfigRepository(dbs.session_factory), "data/test-models")
    f = AnalysisFilters((TEST_CPV,), DAY, DAY)

    preview = await svc.preview(f)
    assert preview["n_items"] == 41
    options = {o["code"]: o["n"] for o in await repo.cpv_options("9999", 30)}
    assert options[TEST_CPV] == 41  # пошук кодів з кількістю позицій з ціною (разом з нащадками)
    assert preview["homogeneity"]["cpv_classes"] == 1

    req = await svc.submit(None, f)
    assert req["status"] == "queued" and not req["from_cache"]
    claimed = await repo.claim_next_request()
    while claimed and claimed["id"] != req["id"]:  # чужі запити в черзі тесту не стосуються
        await repo.finish_request(claimed["id"], "queued")
        claimed = await repo.claim_next_request()
    await svc.process(claimed)

    return repo, svc, f, await repo.get_request(req["id"])


async def test_full_cycle_with_cache(dbs):
    repo, svc, f, done = await _run_cycle(dbs)
    assert done["status"] == "done" and done["model_run_id"]
    items, total = await repo.anomalies(done["model_run_id"], True, None, 10, 0)
    assert total >= 1
    top = items[0]
    assert top["tender_code"] == "UA-TEST-40" and top["price_ratio"] > 5
    assert top["entity_name"] == "Тестовий замовник"
    cats = await repo.categories(done["model_run_id"])
    assert cats[0]["cpv_code"] == TEST_CPV and cats[0]["analysed"]

    # той самий запит з тими самими даними й параметрами — миттєво з кешу, без навчання
    # і без повторного завантаження вибірки (однорідність береться з попереднього запиту)
    async def no_load(_):
        raise AssertionError("вибірка не має завантажуватися при влученні в кеш")

    load_profile, repo.load_profile = repo.load_profile, no_load
    again = await svc.submit(None, f)
    repo.load_profile = load_profile
    assert again["homogeneity_details"] == done["homogeneity_details"]
    assert again["status"] == "done" and again["from_cache"]
    assert again["model_run_id"] == done["model_run_id"]

    # зміна параметрів — інший ключ кешу
    other = await svc.submit(None, f, {"z_strong": 5.0})
    assert other["status"] == "queued" and other["cache_key"] != again["cache_key"]


async def test_item_card_verdicts_and_points(dbs):
    """Картка позиції з аналогами, вердикт, пошук і статистика вердиктів, точки для графіка."""
    repo, _, _, done = await _run_cycle(dbs)
    run = done["model_run_id"]
    top = (await repo.anomalies(run, True, None, 1, 0))[0][0]
    verdicts = SqlVerdictRepository(dbs.session_factory)

    card = await verdicts.item_card(top["item_id"], run)
    assert card["result"]["model_unit"] == "KGM" and card["result"]["model_price"] == pytest.approx(500)
    assert len(card["analogs"]) == 10 and all(a["item_id"] != top["item_id"] for a in card["analogs"])
    assert (await verdicts.item_card(-1, run)) is None

    try:
        v = await verdicts.upsert(None, top["item_id"], top["result_id"], "confirmed", "overpriced", None)
        rows, total = await verdicts.search("confirmed", "overpriced", None, 50, 0)
        assert total >= 1 and any(r["id"] == v["id"] for r in rows)
        assert any(r["status"] == "confirmed" for r in (await verdicts.stats())["by_status_reason"])
        assert {"item_id": top["item_id"], "status": "confirmed", "reason": "overpriced"} in (
            await verdicts.labels()
        )
        queue, _ = await repo.anomalies(run, True, None, 10, 0)
        assert next(q for q in queue if q["item_id"] == top["item_id"])["verdict_status"] == "confirmed"
    finally:
        async with dbs.session_factory() as s, s.begin():
            await s.execute(delete(Verdict).where(Verdict.item_id == top["item_id"]))

    points = await repo.points(run, top["category_id"], 100)
    assert len(points) == 41 and max(p["price"] for p in points) == pytest.approx(500)
