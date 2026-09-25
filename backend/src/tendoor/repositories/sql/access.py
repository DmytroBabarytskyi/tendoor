"""Користувачі, журнал аудиту та параметри аналізу (A4) у PostgreSQL."""

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tendoor.repositories.base import AuditEntry, UserData
from tendoor.repositories.sql.models import AppUser, AuditLog, PipelineConfig, Role


async def set_actor(session: AsyncSession, actor_id: int | None) -> None:
    """Передає автора змін тригеру trg_audit (діє до кінця поточної транзакції)."""
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": "" if actor_id is None else str(actor_id)},
    )


def _user(u: AppUser, role: str) -> UserData:
    return UserData(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=role,
        is_active=u.is_active,
        token_version=u.token_version,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )


_USER_SELECT = select(AppUser, Role.code).join(Role, Role.id == AppUser.role_id)


class SqlUserRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get(self, user_id: int) -> UserData | None:
        async with self._sf() as s:
            row = (await s.execute(_USER_SELECT.where(AppUser.id == user_id))).first()
            return _user(*row) if row else None

    async def get_with_hash(self, email: str) -> tuple[UserData, str] | None:
        async with self._sf() as s:
            row = (await s.execute(_USER_SELECT.where(func.lower(AppUser.email) == email.lower()))).first()
            return (_user(*row), row[0].password_hash) if row else None

    async def get_hash(self, user_id: int) -> str | None:
        async with self._sf() as s:
            return (await s.execute(select(AppUser.password_hash).where(AppUser.id == user_id))).scalar()

    async def list_all(self) -> list[UserData]:
        async with self._sf() as s:
            return [_user(*r) for r in (await s.execute(_USER_SELECT.order_by(AppUser.id))).all()]

    async def count(self) -> int:
        async with self._sf() as s:
            return (await s.execute(select(func.count()).select_from(AppUser))).scalar_one()

    async def roles(self) -> list[tuple[str, str]]:
        async with self._sf() as s:
            return [tuple(r) for r in (await s.execute(select(Role.code, Role.name).order_by(Role.id))).all()]

    async def _role_id(self, s: AsyncSession, role: str) -> int:
        role_id = (await s.execute(select(Role.id).where(Role.code == role))).scalar()
        if role_id is None:
            raise ValueError(f"невідома роль: {role}")
        return role_id

    async def create(
        self, actor_id: int | None, email: str, full_name: str, role: str, password_hash: str
    ) -> UserData:
        async with self._sf() as s, s.begin():
            await set_actor(s, actor_id)
            user = AppUser(
                email=email.lower(),
                full_name=full_name,
                password_hash=password_hash,
                role_id=await self._role_id(s, role),
            )
            s.add(user)
            await s.flush()
            await s.refresh(user)
            return _user(user, role)

    async def update(self, actor_id: int | None, user_id: int, **fields) -> UserData | None:
        async with self._sf() as s, s.begin():
            await set_actor(s, actor_id)
            values = {k: v for k, v in fields.items() if k in ("full_name", "is_active", "password_hash")}
            if "role" in fields:
                values["role_id"] = await self._role_id(s, fields["role"])
            if "password_hash" in values or fields.get("is_active") is False:
                # зміна пароля або блокування завершують усі активні сесії користувача
                values["token_version"] = AppUser.token_version + 1
            if values:
                res = await s.execute(update(AppUser).where(AppUser.id == user_id).values(**values))
                if res.rowcount == 0:
                    return None
            row = (await s.execute(_USER_SELECT.where(AppUser.id == user_id))).first()
            return _user(*row) if row else None

    async def bump_token_version(self, user_id: int) -> None:
        async with self._sf() as s, s.begin():
            await s.execute(
                update(AppUser).where(AppUser.id == user_id).values(token_version=AppUser.token_version + 1)
            )

    async def touch_login(self, user_id: int) -> None:
        async with self._sf() as s, s.begin():
            await s.execute(update(AppUser).where(AppUser.id == user_id).values(last_login_at=func.now()))


class SqlAuditRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def log(
        self,
        user_id: int | None,
        action: str,
        entity: str,
        entity_key: str | None = None,
        payload: dict | None = None,
        ip: str | None = None,
    ) -> None:
        async with self._sf() as s, s.begin():
            s.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    entity=entity,
                    entity_key=entity_key,
                    payload=payload,
                    ip=ip,
                )
            )

    async def search(
        self, entity: str | None, user_id: int | None, action: str | None, limit: int, offset: int
    ) -> tuple[list[AuditEntry], int]:
        q = select(AuditLog, AppUser.email).outerjoin(AppUser, AppUser.id == AuditLog.user_id)
        if entity:
            q = q.where(AuditLog.entity == entity)
        if user_id:
            q = q.where(AuditLog.user_id == user_id)
        if action:
            q = q.where(AuditLog.action == action)
        async with self._sf() as s:
            total = (await s.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
            rows = (await s.execute(q.order_by(AuditLog.id.desc()).limit(limit).offset(offset))).all()
        return [
            AuditEntry(
                id=a.id,
                user_id=a.user_id,
                user_email=email,
                action=a.action,
                entity=a.entity,
                entity_key=a.entity_key,
                payload=a.payload,
                ip=a.ip,
                created_at=a.created_at,
            )
            for a, email in rows
        ], total


def _cfg(c: PipelineConfig) -> dict:
    return {
        "key": c.key,
        "value": c.value,
        "description": c.description,
        "updated_by": c.updated_by,
        "updated_at": c.updated_at,
    }


class SqlConfigRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def list_all(self) -> list[dict]:
        async with self._sf() as s:
            return [
                _cfg(c)
                for c in (await s.execute(select(PipelineConfig).order_by(PipelineConfig.key))).scalars()
            ]

    async def get(self, key: str) -> dict | None:
        async with self._sf() as s:
            c = await s.get(PipelineConfig, key)
            return _cfg(c) if c else None

    async def set(self, actor_id: int, key: str, value: dict) -> dict | None:
        async with self._sf() as s, s.begin():
            await set_actor(s, actor_id)
            c = await s.get(PipelineConfig, key)
            if c is None:
                return None
            c.value, c.updated_by = value, actor_id
            await s.flush()
            await s.refresh(c)
            return _cfg(c)
