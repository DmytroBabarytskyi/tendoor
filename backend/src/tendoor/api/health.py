"""Перевірка стану сервісу та доступності сховищ."""

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from tendoor import __version__

Probe = Callable[[], Awaitable[None]]

router = APIRouter(tags=["service"])


class HealthOut(BaseModel):
    status: str
    version: str
    checks: dict[str, str]


async def _run(probe: Probe, timeout: float = 3.0) -> str:
    try:
        await asyncio.wait_for(probe(), timeout)
        return "ok"
    except Exception as exc:  # стан сховища — дані для відповіді, а не помилка API
        return f"error: {type(exc).__name__}"


@router.get("/health", response_model=HealthOut)
async def health(request: Request, response: Response) -> HealthOut:
    probes: dict[str, Probe] = request.app.state.probes
    names = list(probes)
    results = await asyncio.gather(*(_run(probes[n]) for n in names))
    checks = dict(zip(names, results, strict=True))
    healthy = all(r == "ok" for r in results)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(status="ok" if healthy else "degraded", version=__version__, checks=checks)
