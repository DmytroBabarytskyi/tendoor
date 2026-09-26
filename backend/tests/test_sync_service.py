"""A1: синхронізація фіду Prozorro і нормалізація Bronze → Silver на фейках (без мережі та БД)."""

import asyncio
from datetime import UTC, date, datetime

import pytest

from tendoor.infra.prozorro import FeedEntry, FeedPage
from tendoor.repositories.base import SyncJobData
from tendoor.services.sync import NormalizationService, SyncService
from tendoor.worker.__main__ import _loop

FIXTURES = ("reporting_unit_value", "lot_single_item_contract", "multi_item_no_prices")


class FakeClient:
    def __init__(self, pages: list[list[str]], docs: dict[str, dict | Exception]) -> None:
        self.pages, self.docs, self.feed_args = pages, docs, None

    async def feed(self, start, until, offset=None, limit=500):
        self.feed_args = (start, until, offset)
        for n, ids in enumerate(self.pages, 1):
            now = datetime.now(UTC)
            yield FeedPage([FeedEntry(i, now) for i in ids], f"offset-{n}")

    async def get_tenders(self, ids):
        return [self.docs[i] for i in ids]


class FakeRaw:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}
        self.normalized: set[str] = set()

    async def upsert_many(self, docs):
        for d in docs:
            self.docs[d["id"]] = d
            self.normalized.discard(d["id"])
        return len(docs)

    async def pending_normalization(self, limit):
        return [d for i, d in self.docs.items() if i not in self.normalized][:limit]

    async def mark_normalized(self, ids):
        self.normalized.update(ids)


class FakeProcurement:
    def __init__(self) -> None:
        self.saved = []

    async def save_tenders(self, tenders):
        self.saved += tenders


class FakeJobs:
    def __init__(self) -> None:
        self.progress: list[dict] = []

    async def update_progress(self, job_id, **fields):
        self.progress.append(fields)


@pytest.fixture
def docs(load_fixture) -> dict[str, dict]:
    return {d["id"]: d for d in (load_fixture(n) for n in FIXTURES)}


def _job(cpv: list[str]) -> SyncJobData:
    return SyncJobData(1, "running", date(2026, 9, 25), date(2026, 9, 25), cpv, [], last_offset="resume-here")


def test_period_uses_kyiv_day_boundaries():
    start, end = SyncService.period(date(2026, 9, 25), date(2026, 9, 26))
    assert start == datetime(2026, 9, 24, 21, tzinfo=UTC)  # 00:00 за Києвом (UTC+3)
    assert end.isoformat() == "2026-09-26T20:59:59.999999+00:00"


async def test_sync_filters_saves_normalizes_and_tracks_progress(docs):
    ids = list(docs)
    broken = "0" * 32
    client = FakeClient([ids[:2], [ids[2], broken]], {**docs, broken: RuntimeError("timeout")})
    raw, proc, jobs = FakeRaw(), FakeProcurement(), FakeJobs()
    sync = SyncService(client, raw, jobs, NormalizationService(raw, proc, batch_size=1))
    job = _job(["03", "18"])  # овочі та одяг; комп'ютерна техніка (30…) не потрапляє

    await sync.run(job)

    assert client.feed_args[2] == "resume-here"  # продовження з останнього offset
    assert set(raw.docs) == {ids[0], ids[2]}
    assert {t.prozorro_id for t in proc.saved} == {ids[0], ids[2]}
    assert raw.normalized == set(raw.docs)
    assert jobs.progress[-1] == {
        "scanned": 4,
        "saved": 2,
        "errors": 1,
        "normalized": 2,
        "last_offset": "offset-2",
    }
    assert [p["last_offset"] for p in jobs.progress] == ["offset-1", "offset-2"]


async def test_broken_document_is_marked_and_counted(docs):
    raw, proc = FakeRaw(), FakeProcurement()
    good = next(iter(docs.values()))
    await raw.upsert_many([good, {"id": "broken", "items": "not-a-list"}])
    done, failed = await NormalizationService(raw, proc).run()
    assert (done, failed) == (1, 1)
    assert raw.normalized == {good["id"], "broken"}  # зламаний не обробляється повторно


async def test_worker_loop_handles_tasks_and_survives_claim_errors():
    stop = asyncio.Event()
    queue = [RuntimeError("db down"), "task-1", None, "task-2"]
    handled = []

    async def claim():
        item = queue.pop(0) if queue else None
        if isinstance(item, Exception):
            raise item
        return item

    async def handle(task):
        handled.append(task)
        if task == "task-2":
            stop.set()

    await asyncio.wait_for(_loop("test", stop, 0.01, claim, handle), timeout=5)
    assert handled == ["task-1", "task-2"]


async def test_periodic_job_survives_errors_and_stops():
    from tendoor.worker.__main__ import _periodic

    stop = asyncio.Event()
    calls = []

    async def job():
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("БД недоступна")  # перша спроба падає, наступні тривають
        if len(calls) == 3:
            stop.set()

    await asyncio.wait_for(_periodic("test", stop, every=0.01, job=job, delay=0), timeout=5)
    assert calls == [0, 1, 2]
