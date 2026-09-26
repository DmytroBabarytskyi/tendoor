"""Обслуговування сховища: видалення результатів аналізу, якими давно не користувалися.

Виконується worker'ом раз на добу. Термін зберігання задає адміністратор (параметр retention).
"""

import logging
import time
from pathlib import Path

from tendoor.repositories.base import ConfigRepository
from tendoor.repositories.sql.analysis import SqlAnalysisRepository

log = logging.getLogger(__name__)

RETENTION_KEY = "retention"
DEFAULT_DAYS = 90
FILE_GRACE_SECONDS = 3600  # свіжий файл може належати запуску, який саме зберігається


class MaintenanceService:
    def __init__(self, repo: SqlAnalysisRepository, config: ConfigRepository, model_dir: str) -> None:
        self._repo, self._config, self._dir = repo, config, Path(model_dir)

    async def retention_days(self) -> int:
        cfg = (await self._config.get(RETENTION_KEY) or {}).get("value", {})
        try:
            return max(0, int(cfg.get("model_runs_days", DEFAULT_DAYS)))
        except (TypeError, ValueError):
            log.warning("Некоректний параметр retention: %s — використано %s днів", cfg, DEFAULT_DAYS)
            return DEFAULT_DAYS

    async def run(self) -> tuple[int, int]:
        """Повертає (видалено запусків, видалено файлів артефактів)."""
        days = await self.retention_days()
        if days == 0:
            return 0, 0
        runs = await self._repo.purge_stale_runs(days)
        files = self._sweep(await self._repo.artifact_paths())
        if runs or files:
            log.info(
                "Очищення: видалено запусків %s, файлів артефактів %s (термін %s дн.)", runs, files, days
            )
        return runs, files

    def _sweep(self, referenced: set[str]) -> int:
        if not self._dir.is_dir():
            return 0
        keep = {Path(p).name for p in referenced}
        now, removed = time.time(), 0
        for f in self._dir.glob("*.joblib"):
            if f.name not in keep and now - f.stat().st_mtime > FILE_GRACE_SECONDS:
                f.unlink(missing_ok=True)
                removed += 1
        return removed
