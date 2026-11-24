"""Базові детектори для порівняння: статистичні правила і загальновживані некеровані методи.

Кожна функція повертає оцінку аномальності (більше — підозріліше) з індексом вхідного DataFrame.
"""

import numpy as np
import pandas as pd
from scipy.stats import rankdata, skew
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor


def _log_price(df: pd.DataFrame) -> pd.Series:
    return np.log(df["unit_price_base"].astype(float))


def sigma3_score(df: pd.DataFrame, cpv_digits: int = 4) -> pd.Series:
    """|z| log-ціни в межах «базова одиниця + клас ДК 021» (правило трьох сигм: позначка при > 3)."""
    lp = _log_price(df)
    g = lp.groupby([df["base_unit_code"], df["cpv_code"].fillna("").str[:cpv_digits]])
    z = (lp - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    return z.abs().fillna(0)


def iqr_score(df: pd.DataFrame, cpv_digits: int = 4, min_size: int = 10) -> pd.Series:
    """Відстань log-ціни за межі [Q1, Q3] у міжквартильних розмахах (правило Тьюкі: позначка при > 1,5)."""
    lp = _log_price(df)
    g = lp.groupby([df["base_unit_code"], df["cpv_code"].fillna("").str[:cpv_digits]])
    q1, q3 = g.transform(lambda s: s.quantile(0.25)), g.transform(lambda s: s.quantile(0.75))
    iqr = (q3 - q1).replace(0, np.nan)
    d = np.maximum(q1 - lp, lp - q3) / iqr
    return d.where(g.transform("size") >= min_size).fillna(0).clip(lower=0)


def ecod(x: np.ndarray) -> np.ndarray:
    """ECOD (Li et al., 2022): хвостові ймовірності за емпіричними функціями розподілу кожної ознаки."""
    x = np.asarray(x, float)
    if x.ndim == 1:
        x = x[:, None]
    n = len(x)
    left = -np.log(rankdata(x, axis=0, method="max") / n)
    right = -np.log(rankdata(-x, axis=0, method="max") / n)
    sk = np.nan_to_num(skew(x, axis=0))
    auto = np.where(sk < 0, left, right)
    return np.maximum.reduce([left.sum(1), right.sum(1), auto.sum(1)])


def per_group(values: pd.Series, groups: pd.Series, method: str, seed: int = 42) -> pd.Series:
    """Одновимірний детектор log-ціни окремо в кожній групі порівнюваних товарів."""
    out = pd.Series(np.nan, index=values.index)
    for _, idx in values.groupby(groups).groups.items():
        v = values.loc[idx].to_numpy(float)[:, None]
        if len(v) < 10:
            continue
        if method == "iforest":
            s = -IsolationForest(n_estimators=200, random_state=seed).fit(v).score_samples(v)
        elif method == "lof":
            lof = LocalOutlierFactor(n_neighbors=min(20, len(v) - 1)).fit(v)
            s = -lof.negative_outlier_factor_
        elif method == "ecod":
            s = ecod(v)
        else:
            raise ValueError(method)
        # ранг у групі — оцінки різних груп порівнянні
        out.loc[idx] = rankdata(s) / len(s)
    return out


def global_detector(x: pd.DataFrame, method: str, seed: int = 42) -> pd.Series:
    """Некерований детектор у просторі ознак калібратора (без розмітки)."""
    v = x.to_numpy(float)
    if method == "iforest":
        s = -IsolationForest(n_estimators=300, random_state=seed).fit(v).score_samples(v)
    elif method == "ecod":
        s = ecod(v)
    else:
        raise ValueError(method)
    return pd.Series(s, index=x.index)
