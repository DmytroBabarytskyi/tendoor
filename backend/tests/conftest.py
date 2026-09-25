import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from tendoor.api.app import create_app
from tests.fakes import PASSWORD, FakeContainer

FIXTURES = Path(__file__).parent / "fixtures"


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
