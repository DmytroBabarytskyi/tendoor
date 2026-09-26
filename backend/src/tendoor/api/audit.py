"""A3: розгляд лоту й вердикт, історія перевірок, звіт."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from tendoor.api.analysis import _own_request, explain
from tendoor.api.deps import CurrentUser, container, require_roles
from tendoor.repositories.base import UserData
from tendoor.services.reports import build_xlsx
from tendoor.services.review import ReviewError

router = APIRouter(tags=["A3 Аудит і звітність"])

AuditorUser = Depends(require_roles("admin", "auditor"))
Status = Literal["confirmed", "not_anomaly", "needs_review"]
Reason = Literal["overpriced", "underpriced", "unit_error", "data_error", "justified", "other"]
State = Literal["in_progress", "submitted", "returned", "approved"]
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


async def _apply(
    request: Request, user: UserData, item_id: int, result_id, action: str, payload: dict | None
):
    if await _repo(request).item_card(item_id, None) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Позицію не знайдено")
    try:
        return await _repo(request).apply(user.id, item_id, result_id, action, payload)
    except ReviewError as exc:
        code = status.HTTP_409_CONFLICT if exc.conflict else status.HTTP_422_UNPROCESSABLE_CONTENT
        if "чотирьох очей" in str(exc):
            code = status.HTTP_403_FORBIDDEN
        raise HTTPException(code, str(exc)) from exc


class TakeIn(BaseModel):
    result_id: int | None = None


class ReviewIn(BaseModel):
    decision: Literal["approve", "return"]
    comment: str | None = Field(default=None, max_length=2000)


@router.post("/items/{item_id}/take")
async def take(item_id: int, request: Request, body: TakeIn | None = None, user: UserData = AuditorUser):
    """Взяти позицію в роботу: інші аудитори бачать, хто її перевіряє."""
    return await _apply(request, user, item_id, body.result_id if body else None, "take", None)


@router.put("/items/{item_id}/verdict")
async def set_verdict(item_id: int, body: VerdictIn, request: Request, user: UserData = AuditorUser):
    """Надіслати висновок на погодження (автор перевірки)."""
    payload = {"status": body.status, "reason": body.reason, "comment": body.comment}
    return await _apply(request, user, item_id, body.result_id, "submit", payload)


@router.post("/items/{item_id}/review")
async def review(item_id: int, body: ReviewIn, request: Request, user: UserData = AuditorUser):
    """Погодити або повернути висновок іншого аудитора (принцип «чотирьох очей»)."""
    return await _apply(request, user, item_id, None, body.decision, {"comment": body.comment})


@router.get("/items/{item_id}/verdict-history")
async def verdict_history(item_id: int, _: CurrentUser, request: Request):
    return await _repo(request).history(item_id)


@router.get("/verdicts")
async def verdicts(
    user: CurrentUser,
    request: Request,
    status_: Status | None = None,
    reason: Reason | None = None,
    state: State | None = None,
    queue: Literal["mine", "review"] | None = None,
    mine: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    """A3.3: перевірки — черги «мої» й «на погодженні» та історія з фільтрами (status_ — висновок)."""
    items, total = await _repo(request).search(
        status_,
        reason,
        user.id if mine else None,
        min(limit, 200),
        max(offset, 0),
        state=state,
        queue=queue,
        me=user.id,
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
