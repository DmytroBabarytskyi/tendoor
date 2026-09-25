"""A3: розгляд лоту й вердикт, історія перевірок, звіт."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from tendoor.api.analysis import _own_request, explain
from tendoor.api.deps import CurrentUser, container, require_roles
from tendoor.repositories.base import UserData
from tendoor.services.reports import build_xlsx

router = APIRouter(tags=["A3 Аудит і звітність"])

AuditorUser = Depends(require_roles("admin", "auditor"))
Status = Literal["confirmed", "not_anomaly", "needs_review"]
Reason = Literal["overpriced", "underpriced", "unit_error", "data_error", "justified", "other"]
MAX_REPORT_ROWS = 5000


class VerdictIn(BaseModel):
    status: Status
    reason: Reason
    comment: str | None = Field(default=None, max_length=2000)
    result_id: int | None = None


def _repo(request: Request):
    return container(request).verdicts


@router.get("/items/{item_id}")
async def item_card(item_id: int, _: CurrentUser, request: Request, run_id: int | None = None):
    """A3.1: картка позиції з поясненням, аналогами групи та вердиктом."""
    card = await _repo(request).item_card(item_id, run_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Позицію не знайдено")
    if card["result"]:
        card["result"]["explanation"] = explain(card["result"])
    return card


@router.put("/items/{item_id}/verdict")
async def set_verdict(item_id: int, body: VerdictIn, request: Request, user: UserData = AuditorUser):
    if body.status == "confirmed" and body.reason == "justified":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Підтверджена аномалія не може бути обґрунтованою"
        )
    if await _repo(request).item_card(item_id, None) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Позицію не знайдено")
    return await _repo(request).upsert(
        user.id, item_id, body.result_id, body.status, body.reason, body.comment
    )


@router.get("/items/{item_id}/verdict-history")
async def verdict_history(item_id: int, _: CurrentUser, request: Request):
    return await _repo(request).history(item_id)


@router.get("/verdicts")
async def verdicts(
    user: CurrentUser,
    request: Request,
    status_: Status | None = None,
    reason: Reason | None = None,
    mine: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    """A3.3: історія перевірок (фільтр status_ — статус вердикту)."""
    items, total = await _repo(request).search(
        status_, reason, user.id if mine else None, min(limit, 200), max(offset, 0)
    )
    return {"total": total, "items": items}


@router.get("/verdicts/stats")
async def verdict_stats(_: CurrentUser, request: Request):
    return await _repo(request).stats()


@router.get("/analysis/requests/{request_id}/report.xlsx")
async def report(request_id: int, user: CurrentUser, request: Request):
    """A3.2: звіт XLSX за результатами аналізу."""
    r = await _own_request(request, request_id, user)
    if r["status"] != "done" or not r["model_run_id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Аналіз ще не завершено")
    c = container(request)
    run = await c.analysis.get_run(r["model_run_id"])
    rows, _ = await c.analysis.anomalies(r["model_run_id"], True, None, MAX_REPORT_ROWS, 0)
    cats = await c.analysis.categories(r["model_run_id"])
    data = build_xlsx(r, run, cats, rows, f"{user.full_name} ({user.email})")
    await _repo(request).log_report(request_id, user.id, "xlsx", len(rows))
    name = f"tendoor-analysis-{request_id}-{date.today():%Y%m%d}.xlsx"
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
