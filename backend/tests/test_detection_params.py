"""Перевизначення параметрів виявлення аналітиком: типи, межі, необов'язковий поріг калібратора."""

import pytest

from tendoor.services.detection import DetectionError, DetectionService
from tests.fakes import FakeConfig


@pytest.fixture
def svc():
    return DetectionService(repo=None, config=FakeConfig(), model_dir="data/test-models")


async def test_defaults_merge_stored_values(svc):
    p = await svc.params()
    assert p["k_max"] == 20  # збережене адміністратором
    assert p["anomaly_threshold"] is None and p["calibrate"] is True


async def test_valid_overrides(svc):
    p = await svc.params({"anomaly_threshold": 0.7, "z_strong": 5, "calibrate": False, "min_group_size": 20})
    assert p["anomaly_threshold"] == 0.7
    assert p["z_strong"] == 5.0 and isinstance(p["z_strong"], float)
    assert p["calibrate"] is False and p["min_group_size"] == 20
    assert (await svc.params({"anomaly_threshold": None}))["anomaly_threshold"] is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"unknown": 1}, "невідомий"),
        ({"calibrate": 1}, "тип"),  # число замість прапорця
        ({"min_group_size": 12.5}, "тип"),
        ({"z_strong": True}, "тип"),
        ({"z_strong": 50}, "межах"),
        ({"anomaly_threshold": 1.5}, "межах"),
        ({"min_group_size": 1}, "межах"),
    ],
)
async def test_invalid_overrides(svc, overrides, message):
    with pytest.raises(DetectionError, match=message):
        await svc.params(overrides)
