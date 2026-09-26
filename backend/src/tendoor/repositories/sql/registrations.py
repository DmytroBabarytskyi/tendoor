"""Заявки на реєстрацію (A4): подання, розгляд адміністратором, створення користувача під час погодження."""

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tendoor.repositories.sql.access import set_actor
from tendoor.repositories.sql.models import AppUser, RegistrationRequest, Role

_FIELDS = (
    "id",
    "email",
    "full_name",
    "requested_role",
    "justification",
    "status",
    "decided_by",
    "decided_at",
    "reject_reason",
    "user_id",
    "created_at",
)
_SELECT = """
    SELECT r.id, r.email, r.full_name, r.requested_role, r.justification, r.status, r.decided_by,
           d.full_name AS decided_by_name, r.decided_at, r.reject_reason, r.user_id, r.created_at
    FROM registration_request r LEFT JOIN app_user d ON d.id = r.decided_by
"""


class RegistrationConflict(ValueError):
    pass


class SqlRegistrationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(
        self, email: str, full_name: str, password_hash: str, role: str, justification: str | None
    ) -> dict:
        try:
            async with self._sf() as s, s.begin():
                r = RegistrationRequest(
                    email=email.lower(),
                    full_name=full_name,
                    password_hash=password_hash,
                    requested_role=role,
                    justification=justification,
                )
                s.add(r)
                await s.flush()
                await s.refresh(r)
                return {f: getattr(r, f) for f in _FIELDS}
        except IntegrityError as exc:
            raise RegistrationConflict("Заявка з таким email уже розглядається") from exc

    async def list(self, status: str | None, limit: int = 100) -> list[dict]:
        cond = " WHERE r.status = :status" if status else ""
        async with self._sf() as s:
            rows = await s.execute(
                text(_SELECT + cond + " ORDER BY r.id DESC LIMIT :limit"), {"status": status, "limit": limit}
            )
            return [dict(r) for r in rows.mappings()]

    async def count_pending(self) -> int:
        async with self._sf() as s:
            return (
                await s.execute(select(func.count()).where(RegistrationRequest.status == "pending"))
            ).scalar_one()

    async def decide(
        self, actor_id: int, request_id: int, approve: bool, role: str | None, reason: str | None
    ) -> dict | None:
        """Погодження створює користувача з хешем пароля із заявки — в тій самій транзакції."""
        async with self._sf() as s, s.begin():
            await set_actor(s, actor_id)
            r = (
                await s.execute(
                    select(RegistrationRequest).where(RegistrationRequest.id == request_id).with_for_update()
                )
            ).scalar_one_or_none()
            if r is None:
                return None
            if r.status != "pending":
                raise RegistrationConflict("Заявку вже розглянуто")
            values: dict = {"decided_by": actor_id, "decided_at": func.now()}
            if approve:
                if (await s.execute(select(AppUser.id).where(func.lower(AppUser.email) == r.email))).first():
                    raise RegistrationConflict("Користувач з таким email уже існує")
                role_id = (await s.execute(select(Role.id).where(Role.code == role))).scalar()
                if role_id is None:
                    raise RegistrationConflict(f"Невідома роль: {role}")
                user = AppUser(
                    email=r.email, full_name=r.full_name, password_hash=r.password_hash, role_id=role_id
                )
                s.add(user)
                await s.flush()
                values |= {"status": "approved", "user_id": user.id}
            else:
                values |= {"status": "rejected", "reject_reason": reason}
            await s.execute(
                update(RegistrationRequest).where(RegistrationRequest.id == request_id).values(**values)
            )
            row = (await s.execute(text(_SELECT + " WHERE r.id = :id"), {"id": request_id})).mappings().one()
            return dict(row)
