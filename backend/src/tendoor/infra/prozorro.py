"""Клієнт публічного API Prozorro 2.5: фід змін тендерів і завантаження документів."""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://public-api.prozorro.gov.ua/api/2.5"


@dataclass(slots=True)
class FeedEntry:
    id: str
    date_modified: datetime


@dataclass(slots=True)
class FeedPage:
    entries: list[FeedEntry]
    next_offset: str


class ProzorroClient:
    """Фід упорядкований за dateModified; offset — непрозорий курсор або unix-час початку."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        concurrency: int = 8,
        retries: int = 4,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": "Tendoor/0.1 (diploma research)"},
            transport=transport,
        )
        self._sem = asyncio.Semaphore(concurrency)
        self._retries = retries

    async def __aenter__(self) -> "ProzorroClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def _get(self, url: str, params: dict | None = None) -> dict:
        delay = 1.0
        for attempt in range(self._retries + 1):
            try:
                async with self._sem:
                    resp = await self._http.get(url, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code == 429 or exc.response.status_code >= 500
                )
                if not retryable or attempt == self._retries:
                    raise
                log.warning("Prozorro %s: %s, повтор через %.0f с", url, exc, delay)
                await asyncio.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    async def feed_page(self, offset: str, limit: int = 500) -> FeedPage:
        data = await self._get("/tenders", params={"offset": offset, "limit": limit})
        entries = [FeedEntry(e["id"], datetime.fromisoformat(e["dateModified"])) for e in data["data"]]
        return FeedPage(entries, data["next_page"]["offset"])

    async def feed(
        self, start: datetime, until: datetime, offset: str | None = None, limit: int = 500
    ) -> AsyncIterator[FeedPage]:
        """Сторінки фіду від start (або збереженого offset) до until включно."""
        cursor = offset or f"{start.timestamp():.0f}"
        while True:
            page = await self.feed_page(cursor, limit)
            entries = [e for e in page.entries if e.date_modified <= until]
            done = not page.entries or len(entries) < len(page.entries)
            yield FeedPage(entries, page.next_offset)
            if done:
                return
            cursor = page.next_offset

    async def get_tender(self, tender_id: str) -> dict:
        return (await self._get(f"/tenders/{tender_id}"))["data"]

    async def get_tenders(self, ids: list[str]) -> list[dict | Exception]:
        """Паралельне завантаження; помилка окремого документа не зупиняє пакет."""
        return await asyncio.gather(*(self.get_tender(i) for i in ids), return_exceptions=True)
