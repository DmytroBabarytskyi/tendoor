"""Фейкові реалізації репозиторіїв для тестів API без баз даних."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from tendoor.repositories.base import SyncJobData


class FakeSyncJobs:
    def __init__(self) -> None:
        self.jobs: dict[int, SyncJobData] = {}

    async def create(self, date_from: date, date_to: date, cpv_prefixes, categories) -> SyncJobData:
        job = SyncJobData(
            id=len(self.jobs) + 1,
            status="queued",
            date_from=date_from,
            date_to=date_to,
            cpv_prefixes=cpv_prefixes,
            categories=categories,
            created_at=datetime.now(UTC),
        )
        self.jobs[job.id] = job
        return job

    async def get(self, job_id: int):
        return self.jobs.get(job_id)

    async def list_recent(self, limit: int = 20):
        return sorted(self.jobs.values(), key=lambda j: -j.id)[:limit]


class FakeProcurement:
    async def stats(self) -> dict:
        return {"tenders": 3, "items": 10, "items_priced": 7}


class FakeRaw:
    async def count(self) -> int:
        return 5


@dataclass
class FakeContainer:
    sync_jobs: FakeSyncJobs = field(default_factory=FakeSyncJobs)
    procurement: FakeProcurement = field(default_factory=FakeProcurement)
    raw_tenders: FakeRaw = field(default_factory=FakeRaw)
