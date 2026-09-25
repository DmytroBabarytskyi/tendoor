"""Спільні фікстури. Інтеграційні тести працюють з окремою базою tendoor_test (не з робочими даними):
вона створюється й мігрується автоматично, якщо PostgreSQL доступний."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

# до імпорту застосунку: налаштування читаються з оточення
os.environ.setdefault(
    "TENDOOR_POSTGRES_DSN", "postgresql+asyncpg://tendoor:tendoor@localhost:5432/tendoor_test"
)
os.environ.setdefault("TENDOOR_MONGO_DB", "tendoor_test")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from tendoor.api.app import create_app  # noqa: E402
from tests.fakes import PASSWORD, FakeContainer  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
BACKEND = Path(__file__).parent.parent


async def _ensure_database(dsn: str) -> bool:
    import asyncpg

    url = dsn.replace("postgresql+asyncpg://", "postgresql://")
    base, name = url.rsplit("/", 1)
    try:
        conn = await asyncpg.connect(base + "/postgres", timeout=3)
    except (OSError, asyncpg.PostgresError, TimeoutError):
        return False
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()
    return True


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Створює тестову базу й накочує міграції; без PostgreSQL інтеграційні тести пропускаються."""
    dsn = os.environ["TENDOOR_POSTGRES_DSN"]
    if asyncio.run(_ensure_database(dsn)):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True, capture_output=True
        )
    yield


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf8"))

    return _load


@pytest.fixture
def fake() -> FakeContainer:
    return FakeContainer()


@pytest.fixture
async def client(fake):
    app = create_app(container=fake, probes={})
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c,
    ):
        yield c


@pytest.fixture
def login(client):
    """Повертає заголовки Authorization для користувача з фейкового контейнера."""

    async def _login(email: str, password: str = PASSWORD) -> dict:
        resp = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _login
