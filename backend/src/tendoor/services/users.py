"""A4.2 Керування користувачами й ролями."""

from tendoor.infra.security import hash_password, password_problem
from tendoor.repositories.base import UserData, UserRepository

ROLES = ("admin", "analyst", "auditor")


class UserError(ValueError):
    """Порушення правила керування користувачами (відповідь 400/409)."""

    def __init__(self, message: str, conflict: bool = False) -> None:
        super().__init__(message)
        self.conflict = conflict


class UserService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def create(
        self, actor: UserData | None, email: str, full_name: str, role: str, password: str
    ) -> UserData:
        if role not in ROLES:
            raise UserError(f"невідома роль: {role}")
        if problem := password_problem(password):
            raise UserError(problem)
        if await self._users.get_with_hash(email):
            raise UserError("користувач з таким email вже існує", conflict=True)
        return await self._users.create(
            actor.id if actor else None, email, full_name.strip(), role, hash_password(password)
        )

    async def update(
        self,
        actor: UserData,
        user_id: int,
        full_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        password: str | None = None,
    ) -> UserData | None:
        target = await self._users.get(user_id)
        if target is None:
            return None
        fields: dict = {}
        if full_name is not None:
            fields["full_name"] = full_name.strip()
        if role is not None and role != target.role:
            if role not in ROLES:
                raise UserError(f"невідома роль: {role}")
            fields["role"] = role
        if is_active is not None and is_active != target.is_active:
            fields["is_active"] = is_active
        if password is not None:
            if problem := password_problem(password):
                raise UserError(problem)
            fields["password_hash"] = hash_password(password)

        # Змінювати користувачів може лише активний адміністратор, а собі він не може зняти роль
        # чи заблокувати себе — тож у системі завжди лишається щонайменше один активний адміністратор.
        if target.id == actor.id and (fields.get("is_active") is False or "role" in fields):
            raise UserError("не можна заблокувати себе або змінити власну роль")
        if not fields:
            return target
        return await self._users.update(actor.id, user_id, **fields)
