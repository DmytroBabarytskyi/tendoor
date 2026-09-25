"""A4.1 Автентифікація: вхід, оновлення токенів, вихід, зміна пароля."""

import time
from dataclasses import dataclass

from tendoor.infra.security import (
    TokenError,
    TokenService,
    hash_password,
    needs_rehash,
    password_problem,
    verify_password,
)
from tendoor.repositories.base import AuditRepository, UserData, UserRepository

# хеш для вирівнювання часу відповіді, коли користувача не існує (захист від перебору email)
_DUMMY_HASH = hash_password("dummy-password-for-timing-0")


class AuthError(Exception):
    """Невдала автентифікація; текст безпечно показувати користувачу."""


class TooManyAttempts(AuthError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Забагато невдалих спроб входу. Спробуйте пізніше.")
        self.retry_after = retry_after


class LoginLimiter:
    """Обмеження невдалих спроб входу за парою email+IP (у пам'яті процесу API)."""

    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self._max, self._window = max_failures, window_seconds
        self._fails: dict[str, list[float]] = {}

    def _recent(self, key: str, now: float) -> list[float]:
        fails = [t for t in self._fails.get(key, []) if now - t < self._window]
        self._fails[key] = fails
        return fails

    def check(self, key: str) -> None:
        now = time.monotonic()
        fails = self._recent(key, now)
        if len(fails) >= self._max:
            raise TooManyAttempts(int(self._window - (now - fails[0])) + 1)

    def fail(self, key: str) -> None:
        self._fails.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


@dataclass(slots=True)
class Session:
    user: UserData
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(
        self, users: UserRepository, audit: AuditRepository, tokens: TokenService, limiter: LoginLimiter
    ) -> None:
        self._users, self._audit, self._tokens, self._limiter = users, audit, tokens, limiter

    def _issue(self, u: UserData) -> Session:
        return Session(
            u,
            self._tokens.access_token(u.id, u.role, u.token_version),
            self._tokens.refresh_token(u.id, u.role, u.token_version),
        )

    async def login(self, email: str, password: str, ip: str | None) -> Session:
        key = f"{email.lower()}|{ip}"
        self._limiter.check(key)
        found = await self._users.get_with_hash(email)
        ok = verify_password(found[1] if found else _DUMMY_HASH, password)
        if not found or not ok or not found[0].is_active:
            self._limiter.fail(key)
            await self._audit.log(
                found[0].id if found else None,
                "LOGIN_FAILED",
                "auth",
                payload={"email": email.lower()},
                ip=ip,
            )
            raise AuthError("Невірний email або пароль")
        user, pw_hash = found
        self._limiter.reset(key)
        if needs_rehash(pw_hash):
            await self._users.update(user.id, user.id, password_hash=hash_password(password))
            user = await self._users.get(user.id) or user
        await self._users.touch_login(user.id)
        await self._audit.log(user.id, "LOGIN", "auth", ip=ip)
        return self._issue(user)

    async def refresh(self, refresh_token: str) -> Session:
        try:
            claims = self._tokens.decode(refresh_token, "refresh")
        except TokenError as exc:
            raise AuthError(str(exc)) from exc
        user = await self._users.get(claims.user_id)
        # token_version відрізняється після виходу чи зміни пароля — старі сесії відкликано
        if user is None or not user.is_active or user.token_version != claims.token_version:
            raise AuthError("Сесію завершено, увійдіть знову")
        return self._issue(user)

    async def logout(self, user: UserData, ip: str | None) -> None:
        await self._users.bump_token_version(user.id)
        await self._audit.log(user.id, "LOGOUT", "auth", ip=ip)

    async def change_password(self, user: UserData, old: str, new: str) -> Session:
        current = await self._users.get_hash(user.id)
        if current is None or not verify_password(current, old):
            raise AuthError("Поточний пароль невірний")
        if problem := password_problem(new):
            raise ValueError(problem)
        updated = await self._users.update(user.id, user.id, password_hash=hash_password(new))
        return self._issue(updated)
