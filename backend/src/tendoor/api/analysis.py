"""A2: виявлення аномальних цінових пропозицій — вибірка, запуск, результати, дані для візуалізації."""

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator

from tendoor.api.deps import AnalystUser, CurrentUser, container
from tendoor.ml.calibration import load_calibrator
from tendoor.repositories.base import UserData
from tendoor.repositories.sql.analysis import AnalysisFilters
from tendoor.services.detection import BOUNDS, DetectionError

router = APIRouter(tags=["A2 Виявлення аномалій"])
MAX_DAYS = 366


class SelectionIn(BaseModel):
    cpv_prefixes: list[str] = Field(min_length=1, description="Коди ДК 021 або їх префікси (2–8 цифр)")
    date_from: date
    date_to: date
    unit_codes: list[str] = Field(default_factory=list, description="Базові одиниці; порожньо — усі")

    @field_validator("cpv_prefixes")
    @classmethod
    def _cpv(cls, v: list[str]) -> list[str]:
        v = sorted({p.strip().rstrip("0") if len(p.strip()) == 8 else p.strip() for p in v if p.strip()})
        for p in v:
            if not (p.isdigit() and 2 <= len(p) <= 8):
                raise ValueError(f"некоректний код ДК 021: {p!r}")
        if not v:
            raise ValueError("оберіть хоча б одну категорію")
        return v

    @model_validator(mode="after")
    def _period(self) -> "SelectionIn":
        if self.date_from > self.date_to:
            raise ValueError("date_from пізніше за date_to")
        if (self.date_to - self.date_from).days > MAX_DAYS:
            raise ValueError(f"період не довший за {MAX_DAYS} днів")
        return self

    def filters(self) -> AnalysisFilters:
        return AnalysisFilters(
            tuple(self.cpv_prefixes),
            self.date_from,
            self.date_to,
            tuple(sorted({u.strip().upper() for u in self.unit_codes if u.strip()})),
        )


class RunIn(SelectionIn):
    params: dict[str, Any] = Field(default_factory=dict, description="Перевизначення параметрів (Аналітик)")


class RequestOut(BaseModel):
    id: int
    status: str
    cpv_prefixes: list[str]
    unit_codes: list[str]
    date_from: date
    date_to: date
    params: dict[str, Any]
    homogeneity: float | None
    homogeneity_details: dict[str, Any] | None
    model_run_id: int | None
    from_cache: bool
    message: str | None
    created_at: datetime
    finished_at: datetime | None
    run: dict[str, Any] | None = None


def _svc(request: Request):
    return container(request).detection


def _repo(request: Request):
    return container(request).analysis


def _error(exc: DetectionError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


async def _with_run(request: Request, r: dict) -> dict:
    if r["model_run_id"]:
        run = await _repo(request).get_run(r["model_run_id"])
        if run:
            r["run"] = {
                k: run[k]
                for k in (
                    "id",
                    "pipeline_version",
                    "status",
                    "params",
                    "metrics",
                    "error",
                    "started_at",
                    "finished_at",
                )
            }
    return r


async def _own_request(request: Request, request_id: int, user: UserData) -> dict:
    r = await _repo(request).get_request(request_id)
    # аудитори бачать лише власні запити; аналітик і адміністратор — усі
    if r is None or (user.role == "auditor" and r["user_id"] != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запит не знайдено")
    return r


@router.get("/analysis/params")
async def params(_: AnalystUser, request: Request):
    """Параметри виявлення за замовчуванням і допустимі межі — для перевизначення аналітиком."""
    cal = load_calibrator()
    return {
        "defaults": await _svc(request).params(),
        "bounds": BOUNDS,
        "calibrator_threshold": cal.meta.get("threshold") if cal else None,
    }


@router.get("/analysis/cpv")
async def cpv_options(_: CurrentUser, request: Request, q: str = "", limit: int = 30):
    """Коди ДК 021, за якими є дані, для вибору категорій."""
    return await _repo(request).cpv_options(q, min(limit, 100))


@router.post("/analysis/preview")
async def preview(body: SelectionIn, _: CurrentUser, request: Request):
    """A2.1: оцінка однорідності вибірки до запуску."""
    return await _svc(request).preview(body.filters())


@router.post("/analysis/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(body: RunIn, user: CurrentUser, request: Request):
    if body.params and user.role == "auditor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Змінювати параметри моделі може лише аналітик")
    try:
        r = await _svc(request).submit(user.id, body.filters(), body.params)
    except DetectionError as exc:
        raise _error(exc) from exc
    return await _with_run(request, r)


@router.get("/analysis/requests", response_model=list[RequestOut])
async def list_requests(user: CurrentUser, request: Request, limit: int = 20):
    only_own = user.id if user.role == "auditor" else None
    return await _repo(request).list_requests(only_own, min(limit, 100))


@router.get("/analysis/requests/{request_id}", response_model=RequestOut)
async def get_request(request_id: int, user: CurrentUser, request: Request):
    return await _with_run(request, await _own_request(request, request_id, user))


async def _run_of(request: Request, request_id: int, user: UserData) -> int:
    r = await _own_request(request, request_id, user)
    if r["status"] != "done" or not r["model_run_id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Аналіз ще не завершено")
    return r["model_run_id"]


@router.get("/analysis/requests/{request_id}/categories")
async def categories(request_id: int, user: CurrentUser, request: Request):
    return await _repo(request).categories(await _run_of(request, request_id, user))


@router.get("/analysis/requests/{request_id}/anomalies")
async def anomalies(
    request_id: int,
    user: CurrentUser,
    request: Request,
    only_anomalies: bool = True,
    category_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    signal: Literal["flagged", "risk", "data_error"] = "flagged",
):
    """A2.3: позиції з ризик-балом і поясненням, упорядковані за ризиком.

    Два сигнали: високий ризик (рішення калібратора) і ймовірна помилка даних (екстремум першого етапу,
    позначається незалежно від калібратора). signal обирає, які з них показувати.
    """
    run_id = await _run_of(request, request_id, user)
    rows, total = await _repo(request).anomalies(
        run_id, only_anomalies, category_id, min(limit, 200), max(offset, 0), signal
    )
    for r in rows:
        r["explanation"] = explain(r)
    return {"total": total, "items": rows}


@router.get("/analysis/requests/{request_id}/points")
async def points(request_id: int, category_id: int, user: CurrentUser, request: Request):
    """A2.4: точки групи для діаграм (PCA-проєкція, ціна, обсяг)."""
    return await _repo(request).points(await _run_of(request, request_id, user), category_id)


_PACK_UNIT = {"KGM": "кг", "LTR": "л"}
_UNIT = {**_PACK_UNIT, "H87": "шт", "GRM": "г", "TNE": "т", "MLT": "мл", "MTR": "м", "MTK": "м²", "MTQ": "м³"}


def _n(x: float, d: int = 2) -> str:
    """Число в українському записі: десяткова кома."""
    return f"{x:.{d}f}".replace(".", ",")


def explain(r: dict) -> str:
    """Пояснення для аудитора простою мовою, без статистичних позначень."""
    if r["price_ratio"] is None:
        return "Група замала для статистичного порівняння цін."
    ratio, med = r["price_ratio"], float(r["median_price"] or 0)
    # v2 порівнює ціну в одиниці моделі: «штука» з фасовкою в описі перераховується в грн/кг, грн/л
    code = r.get("model_unit") or r["base_unit_code"]
    unit = _UNIT.get(code, code)
    price = float(r["model_price"] if r.get("model_price") is not None else r["unit_price_base"])
    direction = f"у {_n(ratio, 1)} раза вища" if ratio >= 1 else f"у {_n(1 / ratio, 1)} раза нижча"
    text = f"Ціна {_n(price)} грн/{unit} {direction} за медіану групи ({_n(med)} грн/{unit})"
    if r.get("pack_size"):
        text += f" — перераховано з фасовки {float(r['pack_size']):g} {unit}"
    reasons = []
    if r["is_extreme"]:
        reasons.append("ціна надзвичайно далека від решти цін групи")
    # лише ознаки, що реально впливають на рішення v2 (поріг |z| — як у правилі першого етапу);
    # щільнісний викид (DBSCAN) на рішення калібратора не впливає, тому аудитору не показується
    if r["robust_z"] is not None and abs(r["robust_z"]) >= 4:
        reasons.append(
            f"відхилення в {_n(abs(r['robust_z']), 1)} раза більше за звичайний розкид цін у групі"
        )
    flagged = r["is_anomaly"] or r["is_extreme"]
    text += ". Чому позначено: " + "; ".join(reasons) + "." if reasons and flagged else "."
    if r["is_extreme"]:
        text += (
            " Ймовірна помилка даних: перевірте одиницю виміру, фасовку та чи не вказано суму лоту"
            " замість ціни за одиницю."
        )
    return text
