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
    created_by: int | None = None


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
        self,
        date_from: date,
        date_to: date,
        cpv_prefixes: list[str],
        categories: list[str],
        created_by: int | None = None,
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


# ---------------------------------------------------------------- доступ і аудит (A4)


@dataclass(slots=True)
class UserData:
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    token_version: int
    created_at: datetime | None = None
    last_login_at: datetime | None = None


@dataclass(slots=True)
class AuditEntry:
    id: int
    user_id: int | None
    user_email: str | None
    action: str
    entity: str
    entity_key: str | None
    payload: dict | None
    ip: str | None
    created_at: datetime


class UserRepository(Protocol):
    """actor_id — хто виконує зміну; потрапляє в журнал аудиту через тригер БД."""

    async def get(self, user_id: int) -> UserData | None: ...

    async def get_with_hash(self, email: str) -> tuple[UserData, str] | None: ...

    async def get_hash(self, user_id: int) -> str | None: ...

    async def list_all(self) -> list[UserData]: ...

    async def count(self) -> int: ...

    async def roles(self) -> list[tuple[str, str]]: ...

    async def create(
        self, actor_id: int | None, email: str, full_name: str, role: str, password_hash: str
    ) -> UserData: ...

    async def update(self, actor_id: int | None, user_id: int, **fields) -> UserData | None:
        """fields: full_name, role, is_active, password_hash."""
        ...

    async def bump_token_version(self, user_id: int) -> None: ...

    async def touch_login(self, user_id: int) -> None: ...


class AuditRepository(Protocol):
    async def log(
        self,
        user_id: int | None,
        action: str,
        entity: str,
        entity_key: str | None = None,
        payload: dict | None = None,
        ip: str | None = None,
    ) -> None: ...

    async def search(
        self, entity: str | None, user_id: int | None, action: str | None, limit: int, offset: int
    ) -> tuple[list[AuditEntry], int]: ...


class ConfigRepository(Protocol):
    async def list_all(self) -> list[dict]: ...

    async def get(self, key: str) -> dict | None: ...

    async def set(self, actor_id: int, key: str, value: dict) -> dict | None: ...
