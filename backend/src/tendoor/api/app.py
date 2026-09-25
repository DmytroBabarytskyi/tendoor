"""Створення FastAPI-застосунку."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tendoor import __version__
from tendoor.api import health
from tendoor.config import Settings, get_settings
from tendoor.infra.db import Databases


def create_app(settings: Settings | None = None, probes: dict | None = None) -> FastAPI:
    """probes можна підмінити в тестах, щоб не піднімати реальні БД."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if probes is not None:
            app.state.probes = probes
            yield
            return
        dbs = Databases(settings)
        app.state.dbs = dbs
        app.state.probes = {"postgres": dbs.ping_postgres, "mongo": dbs.ping_mongo}
        try:
            yield
        finally:
            await dbs.close()

    app = FastAPI(
        title="Tendoor API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
