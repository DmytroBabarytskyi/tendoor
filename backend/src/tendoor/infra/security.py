"""Хешування паролів (Argon2id) і токени доступу (JWT, HS256)."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # Argon2id з параметрами бібліотеки за замовчуванням (RFC 9106)

MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Argon2id навмисно повільний (~150 мс і 64 МБ пам'яті на перевірку). У циклі подій він блокував би
# всі інші запити, тому виконується в окремому потоці. Один хеш уже займає parallelism=4 ядра,
# тож кілька паралельних хешів лише витісняли б цикл подій і PostgreSQL (перевірено навантажувальним тестом).
_HASH_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="argon2")


async def hash_password_async(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_HASH_POOL, hash_password, password)


async def verify_password_async(password_hash: str, password: str) -> bool:
    return await asyncio.get_running_loop().run_in_executor(
        _HASH_POOL, verify_password, password_hash, password
    )


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str) -> str | None:
    """Мінімальна політика паролів; None — пароль прийнятний."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"пароль має містити щонайменше {MIN_PASSWORD_LENGTH} символів"
    if password.isdigit() or password.isalpha():
        return "пароль має містити і літери, і цифри або символи"
    return None


class TokenError(Exception):
    pass


@dataclass(slots=True, frozen=True)
class TokenClaims:
    user_id: int
    role: str
    token_version: int
    type: str


class TokenService:
    def __init__(self, secret: str, access_ttl: timedelta, refresh_ttl: timedelta) -> None:
        if len(secret) < 32:
            raise ValueError("JWT secret має бути щонайменше 32 символи")
        self._secret, self._access_ttl, self._refresh_ttl = secret, access_ttl, refresh_ttl

    def _encode(self, claims: TokenClaims, ttl: timedelta) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(claims.user_id),
            "role": claims.role,
            "ver": claims.token_version,
            "typ": claims.type,
            "iat": now,
            "exp": now + ttl,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def access_token(self, user_id: int, role: str, token_version: int) -> str:
        return self._encode(TokenClaims(user_id, role, token_version, "access"), self._access_ttl)

    def refresh_token(self, user_id: int, role: str, token_version: int) -> str:
        return self._encode(TokenClaims(user_id, role, token_version, "refresh"), self._refresh_ttl)

    @property
    def access_ttl_seconds(self) -> int:
        return int(self._access_ttl.total_seconds())

    @property
    def refresh_ttl_seconds(self) -> int:
        return int(self._refresh_ttl.total_seconds())

    def decode(self, token: str, expected_type: str) -> TokenClaims:
        try:
            p = jwt.decode(token, self._secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("токен прострочено") from exc
        except jwt.PyJWTError as exc:
            raise TokenError("недійсний токен") from exc
        if p.get("typ") != expected_type:
            raise TokenError("неправильний тип токена")
        return TokenClaims(int(p["sub"]), p["role"], int(p["ver"]), p["typ"])
