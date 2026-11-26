"""Конвеєр v2: фасовка в описі, калібратор, пояснення в одиниці моделі."""

import numpy as np
import pandas as pd
import pytest

from tendoor.api.analysis import explain
from tendoor.ml.calibration import FEATURES, Calibrator, add_features, load_calibrator
from tendoor.ml.packaging import normalize_packs, parse_pack
from tendoor.ml.pipeline import PIPELINE_VERSION, DetectionParams, prepare, run_detection


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Олія соняшникова 5 л", (5.0, "l")),
        ("Масло вершкове 72,5% 180 г", (0.18, "kg")),
        ("Чай чорний 20х2 г", (0.04, "kg")),
        ("Молоко 900мл пляшка", (0.9, "l")),
        ("Борошно 2 кілограми", (2.0, "kg")),
        ("Сіль кухонна", None),
        ("Кукурудза 72 грн за банку", None),  # «гр» у «грн» — не одиниця фасовки
        ("Цукор 1000 кг", None),  # поза межами правдоподібної фасовки
    ],
)
def test_parse_pack(text, expected):
    got = parse_pack(text)
    if expected is None:
        assert got is None
    else:
        assert got[1] == expected[1] and got[0] == pytest.approx(expected[0])


def test_normalize_packs_converts_only_piece_units():
    d = pd.DataFrame(
        {
            "description_raw": ["Олія 5 л", "Олія 1 л", "Олія 5 л"],
            "base_unit_code": ["H87", "BO", "LTR"],
            "price": [300.0, 70.0, 60.0],
            "qty": [2.0, 10.0, 10.0],
        }
    )
    out = normalize_packs(d)
    assert out["pack_converted"].tolist() == [True, True, False]
    assert out["base_unit_code"].tolist() == ["LTR", "LTR", "LTR"]
    assert out["price"].tolist() == pytest.approx([60.0, 70.0, 60.0])
    assert out["qty"].tolist() == pytest.approx([10.0, 10.0, 10.0])


def _oil_market(n: int = 40, seed: int = 0) -> pd.DataFrame:
    """Олія в літрах і в пляшках 1 л / 5 л: після перерахунку фасовки — одна група з ціною ≈60 грн/л."""
    rng = np.random.default_rng(seed)
    size = rng.choice([1, 5], n)
    unit = np.where(np.arange(n) % 2 == 0, "LTR", "H87")
    price = 60 * np.exp(rng.normal(0, 0.1, n)) * np.where(unit == "H87", size, 1)
    desc = [f"олія соняшникова рафінована {s} л" for s in size]
    return pd.DataFrame(
        {
            "item_id": np.arange(n),
            "description": desc,
            "description_clean": ["олія соняшниковий рафінований"] * n,
            "cpv_code": "15421000",
            "base_unit_code": unit,
            "unit_price_base": price,
            "quantity_base": np.exp(rng.normal(4, 1, n)),
            "price_source": "unit_value",
            "date_published": pd.Timestamp("2026-09-10", tz="UTC"),
        }
    )


def test_pack_normalization_merges_units_into_one_group():
    df = _oil_market()
    v1 = run_detection(df, DetectionParams(pack_normalize=False, calibrate=False))
    v2 = run_detection(df, DetectionParams(calibrate=False))
    assert v2.metrics["n_pack_converted"] == 20
    assert set(v2.items["unit"]) == {"LTR"}
    assert set(v1.items["unit"]) == {"LTR", "H87"}  # v1: пляшки 1 л і 5 л в одній групі «штук»
    assert v2.metrics["n_groups"] < v1.metrics["n_groups"]
    assert v2.items.loc[v2.items["pack_converted"], "price"].between(40, 90).all()


def test_calibrator_learns_from_verdicts_and_roundtrips(tmp_path):
    df = _oil_market(80, seed=1)
    df.loc[3, "unit_price_base"] = 60 * 8
    res = run_detection(df, DetectionParams(calibrate=False))
    d = prepare(df, DetectionParams()).set_index(res.items.index)
    x = add_features(res.items, d)
    assert set(FEATURES) <= set(x.columns)
    assert not x[FEATURES].isna().any().any()
    y = (x["abs_z"] > 3).astype(int).to_numpy().copy()
    y[:5] = 1  # принаймні кілька позитивних прикладів
    cal = Calibrator.fit(x, y, meta={"threshold": 0.5})
    path = tmp_path / "cal.joblib"
    cal.save(path)
    loaded = load_calibrator(path)
    prob = loaded.predict_proba(x)
    assert prob.shape == (len(x),) and ((prob >= 0) & (prob <= 1)).all()
    assert prob[(x["item_id"] == 3).to_numpy()][0] > 0.5
    assert load_calibrator(tmp_path / "missing.joblib") is None


def test_default_run_uses_saved_calibrator():
    df = _oil_market(60, seed=2)
    res = run_detection(df)
    assert PIPELINE_VERSION == "v2.1"
    assert res.metrics["calibrator"]
    risk = res.items["risk"].dropna()
    assert risk.between(0, 100).all()


def test_explain_uses_model_unit_for_converted_packs():
    r = {
        "price_ratio": 2.0,
        "median_price": 60.0,
        "base_unit_code": "H87",
        "unit_price_base": 600.0,
        "model_price": 120.0,
        "model_unit": "LTR",
        "pack_size": 5.0,
        "is_extreme": False,
        "robust_z": 4.2,
        "is_noise": False,
        "is_anomaly": True,
    }
    text = explain(r)
    assert (
        "120,00 грн/л" in text and "фасовки 5 л" in text and "в 4,2 раза більше за звичайний розкид" in text
    )
    legacy = {
        **r,
        "model_price": None,
        "model_unit": None,
        "pack_size": None,
        "base_unit_code": "LTR",
        "unit_price_base": 120.0,
    }
    assert "120,00 грн/л" in explain(legacy) and "фасовки" not in explain(legacy)


def test_shapley_contributions_sum_to_risk_minus_base():
    """Властивість ефективності: Σφ ≈ f(x) − E[f(фон)]; найбільший внесок у різко дорожчої позиції — |z|."""
    from tendoor.ml.explain import FEATURE_LABELS, shapley_values, top_contributions

    df = _oil_market(80, seed=3)
    df.loc[5, "unit_price_base"] = 60 * 9
    res = run_detection(df, DetectionParams(calibrate=False))
    d = prepare(df, DetectionParams()).set_index(res.items.index)
    x = add_features(res.items, d)
    y = (x["abs_z"] > 3).astype(int).to_numpy().copy()
    y[:5] = 1
    cal = Calibrator.fit(x, y)
    target = x[x["item_id"] == 5]
    phi, base = shapley_values(cal, target, x, n_permutations=64)
    assert abs(phi.sum() - (cal.predict_proba(target)[0] - base)) < 0.05
    top = top_contributions(phi, target[FEATURES].to_numpy(dtype=float), FEATURES)[0]
    assert top and set(FEATURE_LABELS) == set(FEATURES)
    assert top[0]["label"] == FEATURE_LABELS[top[0]["feature"]]
    assert abs(top[0]["points"]) >= abs(top[-1]["points"])


def test_default_run_explains_suspicious_items():
    df = _oil_market(60, seed=4)
    df.loc[7, "unit_price_base"] = 60 * 12
    res = run_detection(df)
    flagged = res.items[res.items["is_anomaly"]]
    assert len(flagged) and flagged["contributions"].map(lambda c: isinstance(c, list)).all()
    assert res.metrics["importance"] and res.metrics["importance"][0]["label"]


def test_explain_reports_data_error_even_without_high_risk():
    """Екстремум першого етапу пояснюється як ймовірна помилка даних, навіть коли ризик низький."""
    r = {
        "price_ratio": 950.0,
        "median_price": 40.0,
        "base_unit_code": "KGM",
        "unit_price_base": 38000.0,
        "is_extreme": True,
        "robust_z": 40.0,
        "is_noise": False,
        "is_anomaly": False,
    }
    text = explain(r)
    assert "надзвичайно далека від решти цін" in text and "Ймовірна помилка даних" in text
    normal = {**r, "is_extreme": False, "price_ratio": 1.1, "robust_z": 0.3}
    assert "Ймовірна помилка даних" not in explain(normal)
