"""Бізнес-процес A2 «Виявлення аномальних цінових пропозицій».

A2.1 формування вибірки й оцінка однорідності → A2.2 виявлення аномалій (навчання на вибірці,
повторні запити з тими самими даними й параметрами обслуговуються з кешу) → A2.3 ризик і пояснення
→ A2.4 дані для візуалізації.
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path

import joblib

from tendoor.ml.homogeneity import homogeneity
from tendoor.ml.pipeline import PIPELINE_VERSION, DetectionParams, run_detection
from tendoor.repositories.base import ConfigRepository
from tendoor.repositories.sql.analysis import AnalysisFilters, SqlAnalysisRepository

log = logging.getLogger(__name__)

DEFAULTS_KEY = "detection.defaults"
THRESHOLDS_KEY = "homogeneity.thresholds"
MAX_ITEMS = 100_000  # межа вибірки: навчання має вкладатися приблизно в хвилину


# допустимі межі параметрів, які аналітик може змінити для окремого запиту
BOUNDS: dict[str, tuple[float, float]] = {
    "min_group_size": (5, 200),
    "text_split_min": (10, 500),
    "text_subgroup_min": (3, 100),
    "extreme_iqr_factor": (1.5, 10),
    "z_strong": (2, 10),
    "min_price_z": (1.5, 10),
    "mad_floor": (0.01, 1),
    "anomaly_threshold": (0.05, 0.95),
}


class DetectionError(ValueError):
    pass


def cache_key(filters: AnalysisFilters, fingerprint: str, params: dict) -> str:
    payload = {
        "filters": filters.as_dict(),
        "data": fingerprint,
        "pipeline": PIPELINE_VERSION,
        "params": params,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class DetectionService:
    def __init__(self, repo: SqlAnalysisRepository, config: ConfigRepository, model_dir: str) -> None:
        self._repo, self._config, self._model_dir = repo, config, Path(model_dir)

    async def params(self, overrides: dict | None = None) -> dict:
        """Параметри за замовчуванням (A4.3) + перевизначення аналітика; невідомі ключі відхиляються."""
        stored = (await self._config.get(DEFAULTS_KEY) or {}).get("value", {})
        merged = DetectionParams.from_dict(stored).as_dict()
        kinds = {
            k: f.type if isinstance(f.type, str) else getattr(f.type, "__name__", str(f.type))
            for k, f in DetectionParams.__dataclass_fields__.items()
        }
        for key, value in (overrides or {}).items():
            if key not in merged:
                raise DetectionError(f"невідомий параметр моделі: {key}")
            kind = str(kinds[key])
            is_num = isinstance(value, (int, float)) and not isinstance(value, bool)
            ok = (
                (kind == "bool" and isinstance(value, bool))
                or (kind == "int" and isinstance(value, int) and not isinstance(value, bool))
                or (kind.startswith("float") and is_num)
                or ("None" in kind and value is None)
            )
            if not ok:
                raise DetectionError(f"параметр {key}: некоректний тип значення")
            if value is not None and key in BOUNDS and not BOUNDS[key][0] <= value <= BOUNDS[key][1]:
                lo, hi = BOUNDS[key]
                raise DetectionError(f"параметр {key} має бути в межах {lo}…{hi}")
            merged[key] = float(value) if kind.startswith("float") and value is not None else value
        return merged

    async def preview(self, f: AnalysisFilters) -> dict:
        """A2.1: однорідність і склад вибірки — до запуску навчання."""
        df = await self._repo.load_profile(f)
        thresholds = (await self._config.get(THRESHOLDS_KEY) or {}).get("value", {})
        # обчислення pandas — поза циклом подій, щоб не затримувати інші запити
        h = (
            await asyncio.to_thread(homogeneity, df, thresholds.get("good", 0.7), thresholds.get("warn", 0.4))
        ).as_dict()
        units = df["base_unit_code"].value_counts().head(10) if len(df) else []
        return {
            "n_items": len(df),
            "too_large": len(df) > MAX_ITEMS,
            "homogeneity": h,
            "units": [{"code": c, "n": int(n)} for c, n in (units.items() if len(df) else [])],
            "cpv_classes": [
                {"code": c, "n": int(n)}
                for c, n in (df["cpv_code"].str[:4].value_counts().head(10).items() if len(df) else [])
            ],
        }

    async def submit(self, user_id: int, f: AnalysisFilters, overrides: dict | None = None) -> dict:
        params = await self.params(overrides)
        key = cache_key(f, await self._repo.fingerprint(f), params)
        run = await self._repo.find_run(key)
        cached = run["id"] if run and run["status"] == "done" else None
        # готовий результат для тих самих умов і даних: вибірку повторно не завантажуємо
        h = await self._repo.cached_homogeneity(key) if cached else None
        if h is None:
            preview = await self.preview(f)
            if preview["n_items"] == 0:
                raise DetectionError("за обраними умовами немає позицій з ціною")
            if preview["too_large"]:
                raise DetectionError(
                    f"вибірка перевищує {MAX_ITEMS} позицій — звузьте період або коди ДК 021"
                )
            h = preview["homogeneity"]
        return await self._repo.create_request(user_id, f, overrides or {}, key, h, cached)

    async def process(self, request: dict) -> None:
        """Виконується worker'ом: навчання на вибірці або повторне використання готового запуску."""
        rid, key = request["id"], request["cache_key"]
        existing = await self._repo.find_run(key)
        if existing and existing["status"] == "done":  # інший запит з тим самим ключем уже навчив модель
            await self._repo.finish_request(rid, "done", existing["id"], from_cache=True)
            return
        f = AnalysisFilters(
            tuple(request["cpv_prefixes"]),
            request["date_from"],
            request["date_to"],
            tuple(request["unit_codes"]),
        )
        params = await self.params(request["params"])
        run_id = await self._repo.start_run(key, PIPELINE_VERSION, params)
        try:
            df = await self._repo.load_selection(f)
            result = await asyncio.to_thread(run_detection, df, DetectionParams.from_dict(params))
            artifact = await asyncio.to_thread(self._save_artifact, key, params, result)
            await self._repo.save_results(run_id, result, artifact)
            await self._repo.finish_request(rid, "done", run_id)
            log.info("Запуск %s: %s", run_id, result.metrics)
        except Exception as exc:
            log.exception("Запуск %s завершився помилкою", run_id)
            await self._repo.fail_run(run_id, f"{type(exc).__name__}: {exc}")
            await self._repo.finish_request(rid, "failed", run_id, message=f"{type(exc).__name__}: {exc}")

    def _save_artifact(self, key: str, params: dict, result) -> str | None:
        """Артефакт запуску (параметри, групи, оцінки) — для відтворення експериментів."""
        try:
            self._model_dir.mkdir(parents=True, exist_ok=True)
            path = self._model_dir / f"{key}.joblib"
            joblib.dump(
                {
                    "pipeline": PIPELINE_VERSION,
                    "params": params,
                    "groups": result.groups,
                    "items": result.items,
                    "metrics": result.metrics,
                },
                path,
                compress=3,
            )
            return str(path)
        except OSError:
            log.warning("Не вдалося зберегти артефакт %s", key, exc_info=True)
            return None
