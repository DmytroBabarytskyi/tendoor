"""Експериментальне оцінювання якості: базові статистичні методи та синтетичні аномалії.

Розмітки справжніх порушень немає, тому якість вимірюється на вбудованих аномаліях:
частина позицій отримує ціну, помножену на відомий коефіцієнт (завищення ×3, ×5; заниження ×0.2, ×0.3),
і перевіряється, скільки з них знаходить кожен метод (recall) та скільки позначок хибні (precision).
Базові методи працюють у межах класу ДК 021 (4 цифри) та базової одиниці — як аудитор без ІС.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tendoor.ml.pipeline import DetectionParams, run_detection

FACTORS = (3.0, 5.0, 0.2, 0.3)


def _groups(df: pd.DataFrame) -> pd.core.groupby.SeriesGroupBy:
    return np.log(df["unit_price_base"].astype(float)).groupby(
        [df["base_unit_code"], df["cpv_code"].fillna("").str[:4]]
    )


def sigma3(df: pd.DataFrame) -> pd.Series:
    """Правило трьох сигм для log-ціни в межах класу ДК 021 та одиниці."""
    lp = np.log(df["unit_price_base"].astype(float))
    g = _groups(df)
    z = (lp - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    return (z.abs() > 3).fillna(False)


def iqr_rule(df: pd.DataFrame, k: float = 1.5) -> pd.Series:
    """Правило Тьюкі для log-ціни в межах класу ДК 021 та одиниці."""
    lp = np.log(df["unit_price_base"].astype(float))
    g = _groups(df)
    q1, q3 = g.transform(lambda s: s.quantile(0.25)), g.transform(lambda s: s.quantile(0.75))
    return ((lp < q1 - k * (q3 - q1)) | (lp > q3 + k * (q3 - q1))).fillna(False)


def inject(df: pd.DataFrame, rate: float = 0.03, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    """Копія вибірки з вбудованими аномаліями та мітки (True — змінена позиція)."""
    rng = np.random.default_rng(seed)
    out = df.copy().reset_index(drop=True)
    idx = rng.choice(len(out), size=max(1, int(len(out) * rate)), replace=False)
    factors = rng.choice(FACTORS, size=len(idx))
    out["unit_price_base"] = out["unit_price_base"].astype(float)
    out.loc[idx, "unit_price_base"] = out.loc[idx, "unit_price_base"] * factors
    labels = pd.Series(False, index=out.index)
    labels.iloc[idx] = True
    return out, labels


@dataclass(slots=True)
class Score:
    method: str
    precision: float
    recall: float
    f1: float
    flagged: int

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def _score(method: str, pred: pd.Series, truth: pd.Series) -> Score:
    tp = int((pred & truth).sum())
    fp = int((pred & ~truth).sum())
    fn = int((~pred & truth).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return Score(method, round(precision, 3), round(recall, 3), round(f1, 3), int(pred.sum()))


def evaluate(
    df: pd.DataFrame,
    params: DetectionParams | None = None,
    rate: float = 0.03,
    seeds: tuple[int, ...] = (0, 1, 2),
) -> list[dict]:
    """Середні precision/recall/F1 за кількома прогонами з різними seed."""
    rows = []
    base = df[(df["unit_price_base"].astype(float) > 0) & (df["quantity_base"].astype(float) > 0)]
    for seed in seeds:
        data, truth = inject(base, rate, seed)
        v1 = run_detection(data, params).items
        pred_v1 = pd.Series(False, index=data.index)
        pred_v1.loc[v1.index] = v1["is_anomaly"].to_numpy()
        for method, pred in (("sigma3", sigma3(data)), ("iqr", iqr_rule(data)), ("tendoor-v1", pred_v1)):
            rows.append(_score(method, pred, truth).as_dict() | {"seed": seed})
    table = pd.DataFrame(rows).groupby("method")[["precision", "recall", "f1", "flagged"]].mean().round(3)
    return table.reset_index().to_dict("records")
