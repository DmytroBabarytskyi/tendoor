"""Створення FastAPI-застосунку."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tendoor import __version__
from tendoor.api import admin, analysis, auth, health, sync
from tendoor.config import Settings, get_settings
from tendoor.infra.container import Container


def create_app(settings: Settings | None = None, container=None, probes: dict | None = None) -> FastAPI:
    """container і probes підміняються в тестах, щоб не піднімати реальні БД."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        own = container is None
        c = Container.build(settings) if own else container
        app.state.container = c
        app.state.probes = (
            probes
            if probes is not None
            else {
                "postgres": c.dbs.ping_postgres,
                "mongo": c.dbs.ping_mongo,
            }
        )
        try:
            yield
        finally:
            if own:
                await c.close()

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
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(sync.router, prefix="/api")
    app.include_router(analysis.router, prefix="/api")
    return app


app = create_app()
