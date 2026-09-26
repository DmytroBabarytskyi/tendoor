"""Очищення застарілих результатів: процедура sp_purge_stale_runs і прибирання файлів-сиріт."""

import os
import time
from datetime import date

import pytest
from sqlalchemy import delete, text

from tendoor.config import Settings
from tendoor.infra.db import Databases
from tendoor.repositories.sql.access import SqlConfigRepository
from tendoor.repositories.sql.analysis import AnalysisFilters, SqlAnalysisRepository
from tendoor.repositories.sql.models import AnalysisRequest, ModelRun
from tendoor.services.maintenance import MaintenanceService
from tests.fakes import FakeConfig

pytestmark = pytest.mark.integration
KEY = "maintenance-test-"


@pytest.fixture
async def dbs():
    d = Databases(Settings())
    try:
        async with d.session_factory() as s:
            await s.execute(text("SELECT 1 FROM model_run LIMIT 1"))
    except Exception as exc:
        await d.close()
        pytest.skip(f"PostgreSQL зі схемою недоступний: {type(exc).__name__}")
    yield d
    async with d.session_factory() as s, s.begin():
        await s.execute(delete(AnalysisRequest).where(AnalysisRequest.cache_key.like(f"{KEY}%")))
        await s.execute(delete(ModelRun).where(ModelRun.cache_key.like(f"{KEY}%")))
    await d.close()


async def _run(
    repo, dbs, name: str, age_days: int, request_age_days: int, artifact: str | None = None
) -> tuple[int, int]:
    run_id = await repo.start_run(KEY + name, "v2", {})
    f = AnalysisFilters(("15",), date(2026, 8, 1), date(2026, 8, 31))
    req = await repo.create_request(None, f, {}, KEY + name, {"index": 0.9}, run_id)
    async with dbs.session_factory() as s, s.begin():
        await s.execute(
            text(
                "UPDATE model_run SET status = 'done', artifact_path = :a, "
                "started_at = now() - make_interval(days => :d), "
                "finished_at = now() - make_interval(days => :d) WHERE id = :id"
            ),
            {"id": run_id, "d": age_days, "a": artifact},
        )
        await s.execute(
            text("UPDATE analysis_request SET created_at = now() - make_interval(days => :d) WHERE id = :id"),
            {"id": req["id"], "d": request_age_days},
        )
    return run_id, req["id"]


async def test_purge_removes_only_unused_runs_and_explains_why(dbs, tmp_path):
    repo = SqlAnalysisRepository(dbs.session_factory)
    stale_file, fresh_file, orphan = (
        tmp_path / "stale.joblib",
        tmp_path / "fresh.joblib",
        tmp_path / "orphan.joblib",
    )
    for p in (stale_file, fresh_file, orphan):
        p.write_bytes(b"x")
    hour_ago = time.time() - 7200
    for p in (stale_file, orphan):
        os.utime(p, (hour_ago, hour_ago))
    stale_run, stale_req = await _run(repo, dbs, "stale", 120, 120, str(stale_file))
    # старий запуск, але ним нещодавно скористалися (запит з кешу 5 днів тому) — лишається
    used_run, _ = await _run(repo, dbs, "used", 120, 5, str(fresh_file))

    config = FakeConfig()
    config.items["retention"] = {"key": "retention", "value": {"model_runs_days": 90}}
    runs, files = await MaintenanceService(repo, config, str(tmp_path)).run()

    assert runs >= 1
    assert await repo.get_run(stale_run) is None
    assert await repo.get_run(used_run) is not None
    req = await repo.get_request(stale_req)
    assert req["model_run_id"] is None and "повторіть аналіз" in req["message"]
    assert not stale_file.exists() and not orphan.exists() and fresh_file.exists()
    assert files == 2


async def test_zero_retention_disables_purge(dbs, tmp_path):
    repo = SqlAnalysisRepository(dbs.session_factory)
    run_id, _ = await _run(repo, dbs, "keep", 400, 400)
    config = FakeConfig()
    config.items["retention"] = {"key": "retention", "value": {"model_runs_days": 0}}
    assert await MaintenanceService(repo, config, str(tmp_path)).run() == (0, 0)
    assert await repo.get_run(run_id) is not None


async def test_retention_default_is_seeded(dbs):
    cfg = await SqlConfigRepository(dbs.session_factory).get("retention")
    assert cfg["value"] == {"model_runs_days": 90}
