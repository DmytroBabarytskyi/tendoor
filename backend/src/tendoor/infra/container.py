"""Збирання залежностей: які реалізації репозиторіїв використовуються (SQL/Mongo) — вирішується тут."""

from dataclasses import dataclass

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.repositories.mongo.raw_tenders import MongoRawTenderRepository
from tendoor.repositories.sql.procurement import SqlProcurementRepository
from tendoor.repositories.sql.sync_jobs import SqlSyncJobRepository


@dataclass(slots=True)
class Container:
    settings: Settings
    dbs: Databases
    raw_tenders: MongoRawTenderRepository
    procurement: SqlProcurementRepository
    sync_jobs: SqlSyncJobRepository

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        dbs = Databases(settings)
        return cls(
            settings=settings,
            dbs=dbs,
            raw_tenders=MongoRawTenderRepository(dbs.mongo),
            procurement=SqlProcurementRepository(dbs.session_factory),
            sync_jobs=SqlSyncJobRepository(dbs.session_factory),
        )

    async def close(self) -> None:
        await self.dbs.close()
