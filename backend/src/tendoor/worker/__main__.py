"""Worker: виконує фонові завдання — синхронізацію з Prozorro (A1) і навчання моделей (A2).

Дві черги обробляються паралельно: багатохвилинна синхронізація не затримує аналіз аудитора.
Запуск: python -m tendoor.worker
"""

import asyncio
import contextlib
import logging
import signal
from collections.abc import Awaitable, Callable

from tendoor.config import get_settings
from tendoor.infra.container import Container
from tendoor.infra.prozorro import ProzorroClient
from tendoor.services.maintenance import MaintenanceService
from tendoor.services.sync import NormalizationService, SyncService

log = logging.getLogger("tendoor.worker")


async def _loop(
    name: str,
    stop: asyncio.Event,
    poll: float,
    claim: Callable[[], Awaitable],
    handle: Callable[[object], Awaitable[None]],
) -> None:
    log.info("Черга «%s»: очікування завдань", name)
    while not stop.is_set():
        try:
            task = await claim()
        except Exception:
            log.exception("Черга «%s»: помилка отримання завдання", name)
            task = None
        if task is None:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=poll)
            continue
        await handle(task)


async def _periodic(
    name: str, stop: asyncio.Event, every: float, job: Callable[[], Awaitable], delay: float
) -> None:
    """Періодичне завдання; помилка одного запуску не зупиняє наступні."""
    wait = delay
    while not stop.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=wait)
        if stop.is_set():
            break
        try:
            await job()
        except Exception:
            log.exception("Завдання «%s» завершилося помилкою", name)
        wait = every


async def main() -> None:
    settings = get_settings()
    c = Container.build(settings)
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows: зупинка через Ctrl+C
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)

    await c.raw_tenders.ensure_indexes()
    if n := await c.sync_jobs.requeue_stale():
        log.info("Повернуто в чергу завислих синхронізацій: %s", n)
    if n := await c.analysis.requeue_stale():
        log.info("Повернуто в чергу завислих аналізів: %s", n)

    normalizer = NormalizationService(c.raw_tenders, c.procurement)
    async with ProzorroClient(settings.prozorro_url, concurrency=settings.prozorro_concurrency) as client:
        sync = SyncService(client, c.raw_tenders, c.sync_jobs, normalizer)

        async def run_sync(job) -> None:
            log.info("Синхронізація %s: %s…%s, CPV %s", job.id, job.date_from, job.date_to, job.cpv_prefixes)
            try:
                await sync.run(job)
                await c.sync_jobs.finish(job.id, "done")
            except Exception as exc:
                log.exception("Синхронізація %s завершилася помилкою", job.id)
                await c.sync_jobs.finish(job.id, "failed", f"{type(exc).__name__}: {exc}")

        async def run_analysis(request) -> None:
            log.info(
                "Аналіз %s: CPV %s, %s…%s",
                request["id"],
                request["cpv_prefixes"],
                request["date_from"],
                request["date_to"],
            )
            await c.detection.process(request)

        maintenance = MaintenanceService(c.analysis, c.config, settings.model_dir)
        poll = settings.worker_poll_seconds
        await asyncio.gather(
            _periodic("очищення", stop, 24 * 3600, maintenance.run, delay=60),
            _loop("синхронізація", stop, poll, c.sync_jobs.claim_next, run_sync),
            _loop("аналіз", stop, min(poll, 2.0), c.analysis.claim_next_request, run_analysis),
        )
    await c.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # без рядка на кожен запит до Prozorro
    asyncio.run(main())
