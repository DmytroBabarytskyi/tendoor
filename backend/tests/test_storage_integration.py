"""Черга синхронізацій (PostgreSQL) і сховище Bronze (MongoDB) на реальних базах тестового оточення."""

from datetime import date

import pytest
from sqlalchemy import delete, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.repositories.mongo.raw_tenders import MongoRawTenderRepository
from tendoor.repositories.sql.models import SyncJob
from tendoor.repositories.sql.sync_jobs import SqlSyncJobRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def dbs():
    d = Databases(Settings())
    yield d
    await d.close()


@pytest.fixture
async def jobs(dbs):
    try:
        async with dbs.session_factory() as s:
            await s.execute(text("SELECT 1 FROM sync_job LIMIT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    if "test" not in str(dbs.engine.url.database):
        pytest.skip("черга перевіряється лише в тестовій базі: робочий worker забрав би завдання")
    repo = SqlSyncJobRepository(dbs.session_factory)
    yield repo
    async with dbs.session_factory() as s, s.begin():
        await s.execute(delete(SyncJob))


@pytest.fixture
async def raw(dbs):
    try:
        await dbs.ping_mongo()
    except Exception as exc:
        pytest.skip(f"MongoDB недоступна: {type(exc).__name__}")
    if "test" not in dbs.mongo.name:
        pytest.skip("колекція перевіряється лише в тестовій базі")
    await dbs.mongo["tenders_raw"].drop()
    repo = MongoRawTenderRepository(dbs.mongo)
    await repo.ensure_indexes()
    yield repo
    await dbs.mongo["tenders_raw"].drop()


async def test_sync_job_lifecycle(jobs):
    a = await jobs.create(date(2026, 9, 1), date(2026, 9, 2), ["15"], ["goods"], None)
    b = await jobs.create(date(2026, 9, 3), date(2026, 9, 3), [], [], None)
    assert a.status == "queued" and a.scanned == 0 and a.stats == {}

    claimed = await jobs.claim_next()
    assert claimed.id == a.id and claimed.status == "running" and claimed.started_at
    await jobs.update_progress(a.id, scanned=500, saved=12, last_offset="1758800000.1")
    assert (await jobs.get(a.id)).last_offset == "1758800000.1"

    # зупинка worker посеред синхронізації: завдання повертається в чергу й продовжується з offset
    assert await jobs.requeue_stale() == 1
    again = await jobs.claim_next()
    assert again.id == a.id and again.scanned == 500 and again.started_at == claimed.started_at

    await jobs.finish(a.id, "done")
    done = await jobs.get(a.id)
    assert done.status == "done" and done.finished_at
    assert (await jobs.claim_next()).id == b.id
    assert await jobs.claim_next() is None
    assert [j.id for j in await jobs.list_recent(5)] == [b.id, a.id]
    assert await jobs.get(-1) is None


async def test_raw_upsert_is_idempotent_by_hash(raw, load_fixture):
    doc = load_fixture("reporting_unit_value")
    other = load_fixture("lot_single_item_contract")
    assert await raw.upsert_many([]) == 0
    assert await raw.upsert_many([doc, other]) == 2
    assert await raw.upsert_many([doc]) == 0  # той самий вміст — без запису
    assert await raw.count() == 2

    pending = await raw.pending_normalization(10)
    assert {d["id"] for d in pending} == {doc["id"], other["id"]}
    await raw.mark_normalized([doc["id"]])
    await raw.mark_normalized([])
    assert [d["id"] for d in await raw.pending_normalization(10)] == [other["id"]]

    # змінений документ записується знову й повертається в чергу нормалізації
    changed = {**doc, "dateModified": "2026-09-26T10:00:00+03:00"}
    assert await raw.upsert_many([changed]) == 1
    assert {d["id"] for d in await raw.pending_normalization(10)} == {doc["id"], other["id"]}


async def test_cli_create_user(dbs, capsys):
    """Перший адміністратор на новому розгортанні створюється командою tendoor.cli create-user."""
    from tendoor.cli import create_user
    from tendoor.repositories.sql.models import AppUser

    try:
        await dbs.ping_postgres()
    except Exception as exc:
        pytest.skip(f"PostgreSQL недоступний: {type(exc).__name__}")
    email = "cli-admin@test.dev"
    try:
        assert await create_user(email, "CLI Адмін", "admin", "Strong-pass-2026") == 0
        assert "з роллю admin" in capsys.readouterr().out
        assert await create_user(email, "Дубль", "admin", "Strong-pass-2026") == 1  # email зайнятий
        assert await create_user("not-an-email", "X", "admin", "Strong-pass-2026") == 1
        assert await create_user("weak@test.dev", "X", "admin", "123") == 1  # політика паролів
        assert "некоректний email" in capsys.readouterr().err
    finally:
        async with dbs.session_factory() as s, s.begin():
            await s.execute(
                text(
                    "DELETE FROM audit_log WHERE entity = 'app_user' AND entity_key IN "
                    "(SELECT id::text FROM app_user WHERE email LIKE '%@test.dev')"
                )
            )
            await s.execute(delete(AppUser).where(AppUser.email.in_([email, "weak@test.dev"])))
