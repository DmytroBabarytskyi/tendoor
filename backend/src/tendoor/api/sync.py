"""A1: завдання синхронізації з Prozorro та стан бази закупівель."""

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator

from tendoor.api.deps import AnalystUser, CurrentUser

router = APIRouter(tags=["A1 База закупівель"])

MAX_DAYS = 92
CATEGORIES = {"goods", "services", "works"}


class SyncJobIn(BaseModel):
    date_from: date
    date_to: date
    cpv_prefixes: list[str] = Field(
        default_factory=list, description="Префікси кодів ДК 021, напр. «15» або «1531»"
    )
    categories: list[str] = Field(default_factory=lambda: ["goods"])

    @field_validator("cpv_prefixes")
    @classmethod
    def _cpv(cls, v: list[str]) -> list[str]:
        v = [p.strip() for p in v if p.strip()]
        for p in v:
            if not (p.isdigit() and 2 <= len(p) <= 8):
                raise ValueError(f"некоректний префікс CPV: {p!r} (2–8 цифр)")
        return v

    @field_validator("categories")
    @classmethod
    def _cat(cls, v: list[str]) -> list[str]:
        if bad := set(v) - CATEGORIES:
            raise ValueError(f"невідомі категорії: {sorted(bad)}")
        return v

    @model_validator(mode="after")
    def _period(self) -> "SyncJobIn":
        if self.date_from > self.date_to:
            raise ValueError("date_from пізніше за date_to")
        if (self.date_to - self.date_from).days >= MAX_DAYS:
            raise ValueError(f"період не довший за {MAX_DAYS} днів")
        return self


class SyncJobOut(BaseModel):
    id: int
    status: str
    date_from: date
    date_to: date
    cpv_prefixes: list[str]
    categories: list[str]
    scanned: int
    saved: int
    normalized: int
    errors: int
    message: str | None
    created_by: int | None = None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


def _jobs(request: Request):
    return request.app.state.container.sync_jobs


@router.post("/sync/jobs", response_model=SyncJobOut, status_code=status.HTTP_201_CREATED)
async def create_job(body: SyncJobIn, user: AnalystUser, request: Request):
    return await _jobs(request).create(
        body.date_from, body.date_to, body.cpv_prefixes, body.categories, created_by=user.id
    )


@router.get("/sync/jobs", response_model=list[SyncJobOut])
async def list_jobs(_: AnalystUser, request: Request, limit: int = 20):
    return await _jobs(request).list_recent(min(limit, 100))


@router.get("/sync/jobs/{job_id}", response_model=SyncJobOut)
async def get_job(job_id: int, _: AnalystUser, request: Request):
    job = await _jobs(request).get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Завдання не знайдено")
    return job


@router.get("/procurement/stats")
async def procurement_stats(_: CurrentUser, request: Request) -> dict:
    c = request.app.state.container
    return {**await c.procurement.stats(), "raw_documents": await c.raw_tenders.count()}
