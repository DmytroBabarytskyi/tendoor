from datetime import UTC, datetime

import httpx

from tendoor.infra.prozorro import ProzorroClient

PAGES = {
    "1000": {
        "data": [
            {"id": "a", "dateModified": "2026-01-01T10:00:00+00:00"},
            {"id": "b", "dateModified": "2026-01-01T11:00:00+00:00"},
        ],
        "next_page": {"offset": "p2"},
    },
    "p2": {
        "data": [
            {"id": "c", "dateModified": "2026-01-01T12:00:00+00:00"},
            {"id": "d", "dateModified": "2026-01-02T09:00:00+00:00"},
        ],
        "next_page": {"offset": "p3"},
    },
    "p3": {"data": [], "next_page": {"offset": "p4"}},
}


def _client(handler) -> ProzorroClient:
    return ProzorroClient(base_url="https://api.test", transport=httpx.MockTransport(handler), retries=2)


async def test_feed_stops_after_until():
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = request.url.params["offset"]
        requested.append(offset)
        return httpx.Response(200, json=PAGES[offset])

    start = datetime.fromtimestamp(1000, UTC)
    until = datetime(2026, 1, 1, 23, 59, tzinfo=UTC)
    async with _client(handler) as client:
        pages = [p async for p in client.feed(start, until)]
    assert [e.id for p in pages for e in p.entries] == ["a", "b", "c"]
    assert requested == ["1000", "p2"]  # сторінка p3 не потрібна: «d» уже пізніше за until
    assert pages[-1].next_offset == "p3"


async def test_feed_resumes_from_saved_offset():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAGES[request.url.params["offset"]])

    async with _client(handler) as client:
        pages = [
            p
            async for p in client.feed(
                datetime.fromtimestamp(1000, UTC), datetime(2030, 1, 1, tzinfo=UTC), offset="p2"
            )
        ]
    assert [e.id for p in pages for e in p.entries] == ["c", "d"]


async def test_retries_on_server_error(monkeypatch):
    monkeypatch.setattr("tendoor.infra.prozorro.asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": {"id": "x"}})

    async with _client(handler) as client:
        assert (await client.get_tender("x"))["id"] == "x"
    assert calls["n"] == 3


async def test_client_errors_not_retried(monkeypatch):
    monkeypatch.setattr("tendoor.infra.prozorro.asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    async with _client(handler) as client:
        results = await client.get_tenders(["missing"])
    assert isinstance(results[0], httpx.HTTPStatusError)
    assert calls["n"] == 1


async def _no_sleep(_seconds):
    return None
