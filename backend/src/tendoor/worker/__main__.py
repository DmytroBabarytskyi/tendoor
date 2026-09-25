"""Worker: забирає завдання синхронізації з черги sync_job і виконує їх.

Запуск: python -m tendoor.worker
"""

import asyncio
import contextlib
import logging
import signal

from tendoor.config import get_settings
from tendoor.infra.container import Container
from tendoor.infra.prozorro import ProzorroClient
from tendoor.services.sync import NormalizationService, SyncService

log = logging.getLogger("tendoor.worker")


async def main() -> None:
    settings = get_settings()
    c = Container.build(settings)
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows: зупинка через Ctrl+C
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)

    await c.raw_tenders.ensure_indexes()
    if n := await c.sync_jobs.requeue_stale():
        log.info("Повернуто в чергу завислих завдань: %s", n)

    normalizer = NormalizationService(c.raw_tenders, c.procurement)
    async with ProzorroClient(settings.prozorro_url, concurrency=settings.prozorro_concurrency) as client:
        sync = SyncService(client, c.raw_tenders, c.sync_jobs, normalizer)
        log.info("Worker запущено, очікування завдань")
        while not stop.is_set():
            job = await c.sync_jobs.claim_next()
            if job is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
                continue
            log.info("Завдання %s: %s…%s, CPV %s", job.id, job.date_from, job.date_to, job.cpv_prefixes)
            try:
                await sync.run(job)
                await c.sync_jobs.finish(job.id, "done")
            except Exception as exc:
                log.exception("Завдання %s завершилося помилкою", job.id)
                await c.sync_jobs.finish(job.id, "failed", f"{type(exc).__name__}: {exc}")
    await c.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # без рядка на кожен запит до Prozorro
    asyncio.run(main())
