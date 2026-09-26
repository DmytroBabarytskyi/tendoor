"""A4.1 Реєстрація: заявка на доступ → розгляд адміністратором (погодити з призначенням ролі / відхилити).

Увійти можна лише після погодження; пароль із заявки зберігається тільки як хеш Argon2id і переходить
у створений обліковий запис без повторного введення.
"""

from tendoor.infra.security import hash_password_async, password_problem
from tendoor.repositories.base import UserRepository
from tendoor.repositories.sql.registrations import RegistrationConflict, SqlRegistrationRepository

SELF_SERVICE_ROLES = ("analyst", "auditor")  # роль адміністратора через заявку не видається


class RegistrationError(ValueError):
    def __init__(self, message: str, conflict: bool = False) -> None:
        super().__init__(message)
        self.conflict = conflict


class RegistrationService:
    def __init__(self, repo: SqlRegistrationRepository, users: UserRepository) -> None:
        self._repo, self._users = repo, users

    async def submit(
        self, email: str, full_name: str, role: str, password: str, justification: str | None
    ) -> dict:
        if role not in SELF_SERVICE_ROLES:
            raise RegistrationError("Через заявку можна отримати роль аудитора або аналітика")
        if problem := password_problem(password):
            raise RegistrationError(problem)
        if await self._users.get_with_hash(email):
            raise RegistrationError("Обліковий запис з таким email уже існує — увійдіть", conflict=True)
        try:
            return await self._repo.create(
                email,
                full_name.strip(),
                await hash_password_async(password),
                role,
                (justification or "").strip() or None,
            )
        except RegistrationConflict as exc:
            raise RegistrationError(str(exc), conflict=True) from exc

    async def list(self, status: str | None) -> list[dict]:
        return await self._repo.list(status)

    async def count_pending(self) -> int:
        return await self._repo.count_pending()

    async def approve(self, actor_id: int, request_id: int, role: str) -> dict | None:
        if role not in ("admin", *SELF_SERVICE_ROLES):
            raise RegistrationError(f"Невідома роль: {role}")
        try:
            return await self._repo.decide(actor_id, request_id, True, role, None)
        except RegistrationConflict as exc:
            raise RegistrationError(str(exc), conflict=True) from exc

    async def reject(self, actor_id: int, request_id: int, reason: str) -> dict | None:
        if not reason.strip():
            raise RegistrationError("Вкажіть причину відхилення — її побачить адміністратор у журналі")
        try:
            return await self._repo.decide(actor_id, request_id, False, None, reason.strip())
        except RegistrationConflict as exc:
            raise RegistrationError(str(exc), conflict=True) from exc
