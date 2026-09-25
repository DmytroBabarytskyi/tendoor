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
