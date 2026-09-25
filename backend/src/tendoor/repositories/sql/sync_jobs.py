"""Черга завдань синхронізації в таблиці sync_job."""

from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tendoor.repositories.base import SyncJobData
from tendoor.repositories.sql.models import SyncJob

_FIELDS = [f for f in SyncJobData.__dataclass_fields__]


def _to_data(row: SyncJob) -> SyncJobData:
    return SyncJobData(**{f: getattr(row, f) for f in _FIELDS})


class SqlSyncJobRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(
        self,
        date_from: date,
        date_to: date,
        cpv_prefixes: list[str],
        categories: list[str],
        created_by: int | None = None,
    ) -> SyncJobData:
        async with self._sf() as s, s.begin():
            job = SyncJob(
                status="queued",
                created_by=created_by,
                date_from=date_from,
                date_to=date_to,
                cpv_prefixes=cpv_prefixes,
                categories=categories,
                scanned=0,
                saved=0,
                normalized=0,
                errors=0,
                stats={},
            )
            s.add(job)
            await s.flush()
            await s.refresh(job)
            return _to_data(job)

    async def get(self, job_id: int) -> SyncJobData | None:
        async with self._sf() as s:
            job = await s.get(SyncJob, job_id)
            return _to_data(job) if job else None

    async def list_recent(self, limit: int = 20) -> list[SyncJobData]:
        async with self._sf() as s:
            rows = (await s.execute(select(SyncJob).order_by(SyncJob.id.desc()).limit(limit))).scalars()
            return [_to_data(r) for r in rows]

    async def claim_next(self) -> SyncJobData | None:
        async with self._sf() as s, s.begin():
            job = (
                await s.execute(
                    select(SyncJob)
                    .where(SyncJob.status == "queued")
                    .order_by(SyncJob.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if job is None:
                return None
            job.status = "running"
            job.started_at = job.started_at or func.now()
            await s.flush()
            await s.refresh(job)
            return _to_data(job)

    async def update_progress(self, job_id: int, **fields) -> None:
        async with self._sf() as s, s.begin():
            await s.execute(update(SyncJob).where(SyncJob.id == job_id).values(**fields))

    async def finish(self, job_id: int, status: str, message: str | None = None) -> None:
        await self.update_progress(job_id, status=status, message=message, finished_at=func.now())

    async def requeue_stale(self) -> int:
        async with self._sf() as s, s.begin():
            res = await s.execute(
                update(SyncJob)
                .where(SyncJob.status == "running")
                .values(status="queued", message="перезапуск після зупинки worker")
            )
            return res.rowcount
