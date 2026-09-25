"""Інтерфейси репозиторіїв (DAO). Сервіси залежать лише від них, а не від конкретної СУБД."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from tendoor.services.normalization import NormalizedTender


@dataclass(slots=True)
class SyncJobData:
    id: int
    status: str
    date_from: date
    date_to: date
    cpv_prefixes: list[str]
    categories: list[str]
    scanned: int = 0
    saved: int = 0
    normalized: int = 0
    errors: int = 0
    last_offset: str | None = None
    message: str | None = None
    stats: dict = field(default_factory=dict)
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RawTenderRepository(Protocol):
    """Bronze: сирі документи Prozorro."""

    async def upsert_many(self, docs: list[dict]) -> int:
        """Зберігає нові та змінені документи; повертає їх кількість."""
        ...

    async def pending_normalization(self, limit: int) -> list[dict]:
        """Документи, які ще не перенесено в Silver (або змінилися після цього)."""
        ...

    async def mark_normalized(self, ids: list[str]) -> None: ...

    async def count(self) -> int: ...


class ProcurementRepository(Protocol):
    """Silver: нормалізовані закупівлі."""

    async def save_tenders(self, tenders: list[NormalizedTender]) -> int: ...

    async def stats(self) -> dict: ...


class SyncJobRepository(Protocol):
    async def create(
        self, date_from: date, date_to: date, cpv_prefixes: list[str], categories: list[str]
    ) -> SyncJobData: ...

    async def get(self, job_id: int) -> SyncJobData | None: ...

    async def list_recent(self, limit: int = 20) -> list[SyncJobData]: ...

    async def claim_next(self) -> SyncJobData | None:
        """Атомарно забирає найстаріше завдання зі статусом queued і переводить у running."""
        ...

    async def update_progress(self, job_id: int, **fields) -> None: ...

    async def finish(self, job_id: int, status: str, message: str | None = None) -> None: ...

    async def requeue_stale(self) -> int:
        """Повертає в чергу завдання, що «зависли» в running після аварійного зупинення worker."""
        ...
