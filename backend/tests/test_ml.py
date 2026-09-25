"""Конвеєр v1 на синтетичних даних з відомою відповіддю."""

import numpy as np
import pandas as pd
import pytest

from tendoor.ml.evaluate import inject, iqr_rule, sigma3
from tendoor.ml.homogeneity import homogeneity
from tendoor.ml.pipeline import DetectionParams, assign_groups, knee_eps, prepare, run_detection


def make_items(
    n: int, cpv: str, text: str, price: float, unit: str = "KGM", seed: int = 0, start_id: int = 0
):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "item_id": np.arange(start_id, start_id + n),
            "description_clean": [text] * n,
            "cpv_code": cpv,
            "base_unit_code": unit,
            "unit_price_base": price * np.exp(rng.normal(0, 0.12, n)),  # ±12 % звичайного розкиду
            "quantity_base": np.exp(rng.normal(5, 1, n)),
            "date_published": pd.Timestamp("2026-09-10", tz="UTC")
            + pd.to_timedelta(rng.integers(0, 60, n), "D"),
        }
    )


@pytest.fixture
def market() -> pd.DataFrame:
    potato = make_items(80, "03212100", "картопля свіжа", 18, seed=1)
    butter = make_items(60, "15530000", "масло вершкове 72", 400, seed=2, start_id=100)
    eggs = make_items(40, "03142500", "яйця курячі", 5, unit="H87", seed=3, start_id=200)
    return pd.concat([potato, butter, eggs], ignore_index=True)


def test_groups_follow_cpv_and_unit(market):
    d = prepare(market)
    group, groups = assign_groups(d, DetectionParams())
    assert len(groups) == 3 and all(g.analysed for g in groups)
    # кожна група однорідна за кодом ДК 021 і одиницею
    for g in groups:
        members = d[group == g.label]
        assert members["cpv_code"].nunique() == 1 and members["base_unit_code"].nunique() == 1


def test_small_codes_roll_up_to_parent_category():
    a = make_items(6, "15511100", "молоко пастеризоване", 40)
    b = make_items(6, "15511200", "молоко ультрапастеризоване", 42, start_id=10)
    d = prepare(pd.concat([a, b], ignore_index=True))
    _, groups = assign_groups(d, DetectionParams())
    # по 6 позицій замало для коду, разом 12 — достатньо для категорії 15511
    assert [(g.cpv_code, g.size, g.analysed) for g in groups] == [("15511000", 12, True)]


def test_detects_price_outliers_not_volume_outliers(market):
    df = market.set_index("item_id", drop=False)
    df.loc[5, "unit_price_base"] = 18 * 6  # картопля в 6 разів дорожча
    df.loc[110, "unit_price_base"] = 400 * 0.15  # масло в ~7 разів дешевше
    df.loc[20, "quantity_base"] = 1e7  # величезний обсяг за нормальної ціни — не цінова аномалія
    res = run_detection(df.reset_index(drop=True))
    flagged = set(res.items.loc[res.items["is_anomaly"], "item_id"])
    assert {5, 110} <= flagged
    assert 20 not in flagged
    row = res.items.set_index("item_id").loc[5]
    assert row["ratio"] > 4 and row["risk"] > 80
    assert res.items.set_index("item_id").loc[110, "ratio"] < 0.25
    assert res.metrics["n_analysed"] == len(df)


def test_normal_market_has_few_false_alarms(market):
    res = run_detection(market)
    assert res.metrics["anomaly_share"] < 0.05


def test_groups_below_min_size_are_not_analysed():
    df = make_items(5, "15530000", "масло", 400)
    res = run_detection(df)
    assert res.metrics["n_analysed"] == 0
    assert not res.groups[0].analysed


def test_knee_eps_finds_gap():
    rng = np.random.default_rng(0)
    x = np.vstack([rng.normal(0, 0.1, (100, 2)), [[5, 5], [6, -4]]])
    eps = knee_eps(x, 5)
    assert 0.05 < eps < 2


def test_homogeneity_levels(market):
    single = market[market["cpv_code"] == "03212100"]
    assert homogeneity(single).level == "good"
    mixed = homogeneity(market)
    assert mixed.index < homogeneity(single).index
    assert mixed.units == 2 and mixed.cpv_classes == 3
    assert homogeneity(single.head(20)).level != "good"  # замало позицій
    assert homogeneity(single.iloc[0:0]).level == "bad"


def test_injection_and_baselines(market):
    data, truth = inject(market, rate=0.05, seed=1)
    assert truth.sum() == int(len(market) * 0.05)
    changed = (
        data.loc[truth, "unit_price_base"].to_numpy()
        / market.loc[truth.to_numpy(), "unit_price_base"].to_numpy()
    )
    assert set(np.round(changed, 2)) <= {3.0, 5.0, 0.2, 0.3}
    for pred in (sigma3(data), iqr_rule(data)):
        assert pred.dtype == bool and len(pred) == len(data)
