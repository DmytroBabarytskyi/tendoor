"""Збирання залежностей: які реалізації репозиторіїв використовуються (SQL/Mongo) — вирішується тут."""

from dataclasses import dataclass
from datetime import timedelta

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.infra.security import TokenService
from tendoor.repositories.mongo.raw_tenders import MongoRawTenderRepository
from tendoor.repositories.sql.access import SqlAuditRepository, SqlConfigRepository, SqlUserRepository
from tendoor.repositories.sql.analysis import SqlAnalysisRepository
from tendoor.repositories.sql.procurement import SqlProcurementRepository
from tendoor.repositories.sql.registrations import SqlRegistrationRepository
from tendoor.repositories.sql.sync_jobs import SqlSyncJobRepository
from tendoor.repositories.sql.verdicts import SqlVerdictRepository
from tendoor.services.auth import AuthService, LoginLimiter
from tendoor.services.detection import DetectionService
from tendoor.services.registration import RegistrationService
from tendoor.services.users import UserService


@dataclass(slots=True)
class Container:
    settings: Settings
    dbs: Databases
    raw_tenders: MongoRawTenderRepository
    procurement: SqlProcurementRepository
    sync_jobs: SqlSyncJobRepository
    users: SqlUserRepository
    audit: SqlAuditRepository
    config: SqlConfigRepository
    tokens: TokenService
    auth: AuthService
    user_service: UserService
    analysis: SqlAnalysisRepository
    detection: DetectionService
    verdicts: SqlVerdictRepository
    registrations: RegistrationService

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        dbs = Databases(settings)
        sf = dbs.session_factory
        users, audit = SqlUserRepository(sf), SqlAuditRepository(sf)
        tokens = TokenService(
            settings.jwt_secret,
            timedelta(minutes=settings.access_ttl_minutes),
            timedelta(days=settings.refresh_ttl_days),
        )
        analysis = SqlAnalysisRepository(sf)
        config = SqlConfigRepository(sf)
        limiter = LoginLimiter(settings.login_max_failures, settings.login_lock_minutes * 60)
        return cls(
            settings=settings,
            dbs=dbs,
            raw_tenders=MongoRawTenderRepository(dbs.mongo),
            procurement=SqlProcurementRepository(sf),
            sync_jobs=SqlSyncJobRepository(sf),
            users=users,
            audit=audit,
            config=config,
            tokens=tokens,
            auth=AuthService(users, audit, tokens, limiter),
            user_service=UserService(users),
            analysis=analysis,
            detection=DetectionService(analysis, config, settings.model_dir),
            verdicts=SqlVerdictRepository(sf),
            registrations=RegistrationService(SqlRegistrationRepository(sf), users),
        )

    async def close(self) -> None:
        await self.dbs.close()
