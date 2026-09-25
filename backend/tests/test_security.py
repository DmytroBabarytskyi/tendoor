from datetime import timedelta

import pytest

from tendoor.infra.security import (
    TokenError,
    TokenService,
    hash_password,
    password_problem,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("Correct-horse-1")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "Correct-horse-1")
    assert not verify_password(h, "correct-horse-1")
    assert not verify_password("not-a-hash", "x")
    assert hash_password("same") != hash_password("same")  # сіль


@pytest.mark.parametrize(
    ("password", "ok"),
    [("short1", False), ("onlyletterslong", False), ("12345678901", False), ("Letters-and-1", True)],
)
def test_password_policy(password, ok):
    assert (password_problem(password) is None) == ok


def test_token_types_and_claims():
    ts = TokenService("x" * 32, timedelta(minutes=5), timedelta(days=1))
    claims = ts.decode(ts.access_token(7, "auditor", 3), "access")
    assert (claims.user_id, claims.role, claims.token_version) == (7, "auditor", 3)
    with pytest.raises(TokenError):
        ts.decode(ts.refresh_token(7, "auditor", 3), "access")


def test_short_secret_rejected():
    with pytest.raises(ValueError):
        TokenService("short", timedelta(minutes=5), timedelta(days=1))


async def test_password_hashing_runs_off_the_event_loop():
    """Argon2 (~150 мс) не блокує цикл подій: інші корутини виконуються під час перевірки."""
    import asyncio

    from tendoor.infra.security import hash_password_async, verify_password_async

    h = await hash_password_async("Long-password-1")
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.005)

    t = asyncio.create_task(ticker())
    results = await asyncio.gather(*(verify_password_async(h, p) for p in ["Long-password-1", "wrong"] * 3))
    t.cancel()
    assert results == [True, False] * 3
    assert ticks > 5
