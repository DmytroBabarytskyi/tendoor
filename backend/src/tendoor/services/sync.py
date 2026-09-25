"""Бізнес-процес A1 «Формування бази даних закупівель»: синхронізація та нормалізація."""

import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from tendoor.infra.prozorro import ProzorroClient
from tendoor.repositories.base import (
    ProcurementRepository,
    RawTenderRepository,
    SyncJobData,
    SyncJobRepository,
)
from tendoor.services.normalization import matches_filter, normalize_tender

log = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")  # межі доби рахуються за київським часом, як у Prozorro


class NormalizationService:
    """Переносить нові/змінені документи з Bronze (Mongo) у Silver (PostgreSQL)."""

    def __init__(
        self, raw: RawTenderRepository, procurement: ProcurementRepository, batch_size: int = 200
    ) -> None:
        self._raw, self._proc, self._batch = raw, procurement, batch_size

    async def run(self) -> tuple[int, int]:
        """Повертає (нормалізовано, з помилками)."""
        done = failed = 0
        while docs := await self._raw.pending_normalization(self._batch):
            ok, ids = [], []
            for d in docs:
                try:
                    ok.append(normalize_tender(d))
                except Exception:
                    log.exception("Не вдалося нормалізувати тендер %s", d.get("id"))
                    failed += 1
                ids.append(d["id"])  # зламаний документ теж позначаємо, щоб не зациклитися
            await self._proc.save_tenders(ok)
            await self._raw.mark_normalized(ids)
            done += len(ok)
        return done, failed


class SyncService:
    """Завантажує зміни фіду Prozorro за період, фільтрує й зберігає в Bronze."""

    def __init__(
        self,
        client: ProzorroClient,
        raw: RawTenderRepository,
        jobs: SyncJobRepository,
        normalizer: NormalizationService,
        page_size: int = 500,
    ) -> None:
        self._client, self._raw, self._jobs = client, raw, jobs
        self._normalizer, self._page = normalizer, page_size

    @staticmethod
    def period(date_from: date, date_to: date) -> tuple[datetime, datetime]:
        start = datetime.combine(date_from, time.min, KYIV)
        end = datetime.combine(date_to + timedelta(days=1), time.min, KYIV) - timedelta(microseconds=1)
        return start.astimezone(UTC), end.astimezone(UTC)

    async def run(self, job: SyncJobData) -> None:
        start, until = self.period(job.date_from, job.date_to)
        scanned, saved, errors = job.scanned, job.saved, job.errors
        async for page in self._client.feed(start, until, offset=job.last_offset, limit=self._page):
            ids = [e.id for e in page.entries]
            results = await self._client.get_tenders(ids)
            docs = []
            for tender_id, res in zip(ids, results, strict=True):
                if isinstance(res, Exception):
                    log.warning("Тендер %s не завантажено: %s", tender_id, res)
                    errors += 1
                elif matches_filter(res, job.cpv_prefixes, job.categories):
                    docs.append(res)
            saved += await self._raw.upsert_many(docs)
            scanned += len(ids)
            normalized, failed = await self._normalizer.run()
            await self._jobs.update_progress(
                job.id,
                scanned=scanned,
                saved=saved,
                errors=errors + failed,
                normalized=job.normalized + normalized,
                last_offset=page.next_offset,
            )
            job.normalized += normalized
            errors += failed
            log.info("job %s: переглянуто %s, збережено %s", job.id, scanned, saved)
