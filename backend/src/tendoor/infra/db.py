"""Підключення до PostgreSQL (Silver/Gold) та MongoDB (Bronze)."""

from pymongo import AsyncMongoClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from tendoor.config import Settings


class Databases:
    """Тримає пули з'єднань на весь час життя процесу (API або worker)."""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.mongo_client: AsyncMongoClient = AsyncMongoClient(
            settings.mongo_uri, serverSelectionTimeoutMS=3000
        )
        self.mongo = self.mongo_client[settings.mongo_db]

    async def ping_postgres(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def ping_mongo(self) -> None:
        await self.mongo_client.admin.command("ping")

    async def close(self) -> None:
        await self.engine.dispose()
        await self.mongo_client.close()
