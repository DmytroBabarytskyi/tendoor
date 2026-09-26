"""A2: вибірки для аналізу, запуски моделей (кеш), результати виявлення аномалій."""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tendoor.ml.pipeline import DetectionResult
from tendoor.repositories.sql.models import AnalysisRequest, AnomalyResult, Category, ModelRun


@dataclass(slots=True, frozen=True)
class AnalysisFilters:
    cpv_prefixes: tuple[str, ...]
    date_from: date
    date_to: date
    unit_codes: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "cpv_prefixes": sorted(self.cpv_prefixes),
            "unit_codes": sorted(self.unit_codes),
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
        }


# Вибірка: позиції з визначеною ціною в базовій одиниці за датою оголошення тендера
_WHERE = """
    i.unit_price_base > 0 AND i.quantity_base > 0
    AND t.date_published >= :date_from AND t.date_published < CAST(:date_to AS date) + 1
    AND i.cpv_code LIKE ANY(:patterns)
    AND (cardinality(CAST(:units AS varchar[])) = 0 OR i.base_unit_code = ANY(CAST(:units AS varchar[])))
"""


def _params(f: AnalysisFilters) -> dict:
    return {
        "date_from": f.date_from,
        "date_to": f.date_to,
        "patterns": [p + "%" for p in f.cpv_prefixes],
        "units": list(f.unit_codes),
    }


def _cols(model) -> list[str]:
    return [c.name for c in model.__table__.columns]


def _request(r: AnalysisRequest) -> dict:
    return {c: getattr(r, c) for c in _cols(AnalysisRequest)}


def _run(r: ModelRun) -> dict:
    return {c: getattr(r, c) for c in _cols(ModelRun)}


def _none_if_nan(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


class SqlAnalysisRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    # ------------------------------------------------------------ вибірка

    async def load_selection(self, f: AnalysisFilters) -> pd.DataFrame:
        sql = f"""
            SELECT i.id AS item_id, i.description, i.description_clean, i.cpv_code, i.base_unit_code,
                   i.unit_price_base::float AS unit_price_base, i.quantity_base::float AS quantity_base,
                   i.price_source, t.date_published
            FROM item i JOIN tender t ON t.id = i.tender_id
            WHERE {_WHERE}
            ORDER BY i.id
        """
        async with self._sf() as s:
            rows = (await s.execute(text(sql), _params(f))).mappings().all()
        cols = [
            "item_id",
            "description",
            "description_clean",
            "cpv_code",
            "base_unit_code",
            "unit_price_base",
            "quantity_base",
            "price_source",
            "date_published",
        ]
        return pd.DataFrame(rows, columns=cols)

    async def load_profile(self, f: AnalysisFilters) -> pd.DataFrame:
        """Лише стовпці для оцінки однорідності: у кілька разів легше за повну вибірку з описами."""
        sql = f"""SELECT i.cpv_code, i.base_unit_code, i.unit_price_base::float AS unit_price_base
                  FROM item i JOIN tender t ON t.id = i.tender_id WHERE {_WHERE}"""
        async with self._sf() as s:
            rows = (await s.execute(text(sql), _params(f))).all()
        return pd.DataFrame(rows, columns=["cpv_code", "base_unit_code", "unit_price_base"])

    async def cached_homogeneity(self, cache_key: str) -> dict | None:
        """Однорідність з попереднього запиту з тим самим ключем (ті самі умови й дані)."""
        sql = """SELECT homogeneity_details FROM analysis_request
                 WHERE cache_key = :key AND homogeneity_details IS NOT NULL ORDER BY id DESC LIMIT 1"""
        async with self._sf() as s:
            return (await s.execute(text(sql), {"key": cache_key})).scalar()

    async def fingerprint(self, f: AnalysisFilters) -> str:
        """Версія даних вибірки: зміниться, щойно нормалізація додасть чи змінить позиції."""
        sql = f"""SELECT count(*), coalesce(max(i.id), 0), max(t.date_modified)
                  FROM item i JOIN tender t ON t.id = i.tender_id WHERE {_WHERE}"""
        async with self._sf() as s:
            n, max_id, max_mod = (await s.execute(text(sql), _params(f))).one()
        return f"{n}:{max_id}:{max_mod.isoformat() if max_mod else '-'}"

    async def cpv_options(self, q: str, limit: int = 30) -> list[dict]:
        """Коди ДК 021, для яких є позиції з ціною; пошук за кодом або назвою."""
        # спершу кількість позицій за кодами (~тисяча рядків), потім згортка до предків ієрархії:
        # з'єднання LIKE з усіма позиціями напряму тривало ~4 с, так — ~80 мс
        sql = """
            WITH counts AS (
                SELECT cpv_code, count(*) AS n FROM item WHERE unit_price_base > 0 GROUP BY cpv_code
            )
            SELECT c.code, c.description, c.level, sum(k.n)::int AS n
            FROM cpv c JOIN counts k ON k.cpv_code LIKE rtrim(c.code, '0') || '%'
            WHERE c.description IS NOT NULL
              AND (:q = '' OR c.code LIKE :q || '%' OR c.description ILIKE '%' || :q || '%')
            GROUP BY c.code, c.description, c.level
            ORDER BY n DESC
            LIMIT :limit
        """
        async with self._sf() as s:
            return [
                dict(r) for r in (await s.execute(text(sql), {"q": q.strip(), "limit": limit})).mappings()
            ]

    # ------------------------------------------------------------ запити

    async def create_request(
        self,
        user_id: int,
        f: AnalysisFilters,
        params: dict,
        cache_key: str,
        homogeneity: dict,
        run_id: int | None = None,
    ) -> dict:
        async with self._sf() as s, s.begin():
            r = AnalysisRequest(
                user_id=user_id,
                cpv_prefixes=list(f.cpv_prefixes),
                unit_codes=list(f.unit_codes),
                date_from=f.date_from,
                date_to=f.date_to,
                params=params,
                cache_key=cache_key,
                homogeneity=homogeneity["index"],
                homogeneity_details=homogeneity,
                status="done" if run_id else "queued",
                model_run_id=run_id,
                from_cache=bool(run_id),
                finished_at=func.now() if run_id else None,
            )
            s.add(r)
            await s.flush()
            await s.refresh(r)
            return _request(r)

    async def get_request(self, request_id: int) -> dict | None:
        async with self._sf() as s:
            r = await s.get(AnalysisRequest, request_id)
            return _request(r) if r else None

    async def list_requests(self, user_id: int | None, limit: int = 20) -> list[dict]:
        q = select(AnalysisRequest).order_by(AnalysisRequest.id.desc()).limit(limit)
        if user_id is not None:
            q = q.where(AnalysisRequest.user_id == user_id)
        async with self._sf() as s:
            return [_request(r) for r in (await s.execute(q)).scalars()]

    async def claim_next_request(self) -> dict | None:
        async with self._sf() as s, s.begin():
            r = (
                await s.execute(
                    select(AnalysisRequest)
                    .where(AnalysisRequest.status == "queued")
                    .order_by(AnalysisRequest.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if r is None:
                return None
            r.status = "running"
            await s.flush()
            return _request(r)

    async def finish_request(
        self,
        request_id: int,
        status: str,
        run_id: int | None = None,
        message: str | None = None,
        from_cache: bool = False,
    ) -> None:
        async with self._sf() as s, s.begin():
            await s.execute(
                update(AnalysisRequest)
                .where(AnalysisRequest.id == request_id)
                .values(
                    status=status,
                    model_run_id=run_id,
                    message=message,
                    from_cache=from_cache,
                    finished_at=func.now(),
                )
            )

    async def requeue_stale(self) -> int:
        async with self._sf() as s, s.begin():
            res = await s.execute(
                update(AnalysisRequest).where(AnalysisRequest.status == "running").values(status="queued")
            )
            return res.rowcount

    # ------------------------------------------------------------ запуски та кеш

    async def find_run(self, cache_key: str) -> dict | None:
        async with self._sf() as s:
            r = (
                await s.execute(select(ModelRun).where(ModelRun.cache_key == cache_key))
            ).scalar_one_or_none()
            return _run(r) if r else None

    async def get_run(self, run_id: int) -> dict | None:
        async with self._sf() as s:
            r = await s.get(ModelRun, run_id)
            return _run(r) if r else None

    async def start_run(self, cache_key: str, version: str, params: dict) -> int:
        """Новий запуск; невдалий запуск з тим самим ключем перезапускається."""
        async with self._sf() as s, s.begin():
            existing = (
                await s.execute(select(ModelRun).where(ModelRun.cache_key == cache_key).with_for_update())
            ).scalar_one_or_none()
            if existing:
                existing.status, existing.error, existing.started_at = "running", None, func.now()
                await s.flush()
                return existing.id
            run = ModelRun(cache_key=cache_key, pipeline_version=version, params=params, status="running")
            s.add(run)
            await s.flush()
            return run.id

    async def fail_run(self, run_id: int, error: str) -> None:
        async with self._sf() as s, s.begin():
            await s.execute(
                update(ModelRun)
                .where(ModelRun.id == run_id)
                .values(status="failed", error=error[:2000], finished_at=func.now())
            )

    async def save_results(self, run_id: int, result: DetectionResult, artifact_path: str | None) -> None:
        """Групи й оцінки всіх позицій записуються однією транзакцією разом зі статусом запуску."""
        async with self._sf() as s, s.begin():
            cat_rows = [
                {
                    "model_run_id": run_id,
                    "label": g.label,
                    "base_unit_code": g.unit,
                    "cpv_code": g.cpv_code,
                    "top_terms": g.top_terms,
                    "size": g.size,
                    "median_price": g.median_price,
                    "analysed": g.analysed,
                    "n_anomalies": g.n_anomalies,
                    "details": {
                        "eps": g.eps,
                        "explained_variance": g.explained_variance,
                        "silhouette": g.silhouette,
                    },
                }
                for g in result.groups
            ]
            cat_ids = {}
            if cat_rows:
                res = await s.execute(insert(Category).returning(Category.label, Category.id), cat_rows)
                cat_ids = dict(res.all())
            items = result.items
            rows = [
                {
                    "model_run_id": run_id,
                    "item_id": int(r.item_id),
                    "category_id": cat_ids[int(r.group)],
                    "is_anomaly": bool(r.is_anomaly),
                    "is_extreme": bool(r.is_extreme),
                    "is_noise": bool(r.is_noise),
                    "risk_score": None if np.isnan(r.risk) else round(float(r.risk), 2),
                    "robust_z": _none_if_nan(r.robust_z),
                    "price_ratio": _none_if_nan(r.ratio),
                    "pc1": _none_if_nan(r.pc1),
                    "pc2": _none_if_nan(r.pc2),
                    "model_price": _none_if_nan(r.price),
                    "model_unit": r.unit,
                    "pack_size": _none_if_nan(r.pack_size) if r.pack_converted else None,
                }
                for r in items.itertuples(index=False)
            ]
            for chunk in range(0, len(rows), 5000):
                await s.execute(insert(AnomalyResult), rows[chunk : chunk + 5000])
            await s.execute(
                update(ModelRun)
                .where(ModelRun.id == run_id)
                .values(
                    status="done", metrics=result.metrics, artifact_path=artifact_path, finished_at=func.now()
                )
            )

    # ------------------------------------------------------------ перегляд результатів

    async def anomalies(
        self, run_id: int, only_anomalies: bool, category_id: int | None, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        where = (
            "model_run_id = :run"
            + (" AND is_anomaly" if only_anomalies else "")
            + (" AND category_id = :cat" if category_id else "")
        )
        params = {"run": run_id, "cat": category_id, "limit": limit, "offset": offset}
        async with self._sf() as s:
            total = (
                await s.execute(text(f"SELECT count(*) FROM v_anomaly_queue WHERE {where}"), params)
            ).scalar()
            rows = (
                (
                    await s.execute(
                        text(
                            f"""SELECT * FROM v_anomaly_queue WHERE {where}
                    ORDER BY is_anomaly DESC, risk_score DESC NULLS LAST, result_id
                    LIMIT :limit OFFSET :offset"""
                        ),
                        params,
                    )
                )
                .mappings()
                .all()
            )
        return [dict(r) for r in rows], total

    async def categories(self, run_id: int) -> list[dict]:
        async with self._sf() as s:
            rows = (
                await s.execute(
                    select(Category)
                    .where(Category.model_run_id == run_id)
                    .order_by(Category.analysed.desc(), Category.size.desc())
                )
            ).scalars()
            return [{c: getattr(r, c) for c in _cols(Category)} for r in rows]

    async def points(self, run_id: int, category_id: int, limit: int = 3000) -> list[dict]:
        """Точки для діаграм: PCA-проєкція, ціна, обсяг, мітка аномалії."""
        sql = """SELECT r.item_id, r.pc1, r.pc2, r.is_anomaly, r.is_extreme, r.risk_score,
                        COALESCE(r.model_price, i.unit_price_base::float) AS price,
                        COALESCE(i.quantity_base::float * r.pack_size, i.quantity_base::float) AS quantity
                 FROM anomaly_result r JOIN item i ON i.id = r.item_id
                 WHERE r.model_run_id = :run AND r.category_id = :cat
                 LIMIT :limit"""
        async with self._sf() as s:
            rows = (
                await s.execute(text(sql), {"run": run_id, "cat": category_id, "limit": limit})
            ).mappings()
            return [dict(r) for r in rows]

    async def artifact_paths(self) -> set[str]:
        """Шляхи артефактів, на які ще посилаються запуски (решта файлів — сироти після очищення)."""
        async with self._sf() as s:
            rows = await s.execute(
                text("SELECT artifact_path FROM model_run WHERE artifact_path IS NOT NULL")
            )
            return {r[0] for r in rows}

    async def purge_stale_runs(self, days: int) -> int:
        async with self._sf() as s, s.begin():
            return (await s.execute(text("CALL sp_purge_stale_runs(:d, 0)"), {"d": days})).scalar() or 0
