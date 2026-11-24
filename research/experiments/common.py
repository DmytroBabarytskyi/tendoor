"""Спільне для експериментів статті: дані, мітки, зважені метрики, вкладена крос-валідація калібратора.

Запуск з каталогу backend (віртуальне середовище застосунку):
    cd backend && uv run python ../research/experiments/<скрипт>.py
"""

import asyncio
import glob
import json
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "research" / "annotation"
OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "backend" / "src"))

from tendoor.config import get_settings  # noqa: E402
from tendoor.infra.db import Databases  # noqa: E402
from tendoor.ml.calibration import Calibrator  # noqa: E402
from tendoor.repositories.sql.analysis import AnalysisFilters, SqlAnalysisRepository  # noqa: E402

# еталонна вибірка розмітки: ДК 021 «15», 01.08–30.09.2026 (запит №4 застосунку)
REFERENCE = AnalysisFilters(("15",), date(2026, 8, 1), date(2026, 9, 30))
BUDGET = 0.04  # частка позицій, яку позначає кожен метод (≈ частка позначених v1: 627 / 15 450)


async def _load(filters: AnalysisFilters) -> pd.DataFrame:
    dbs = Databases(get_settings())
    df = await SqlAnalysisRepository(dbs.session_factory).load_selection(filters)
    await dbs.close()
    return df


def load_selection(filters: AnalysisFilters = REFERENCE) -> pd.DataFrame:
    return asyncio.run(_load(filters))


def load_labels(kind: str = "blind") -> pd.DataFrame:
    """item_id, status, y, stratum; kind: blind (сліпа розмітка) або sighted (перша, з рішенням v1)."""
    pattern = "decisions*.json" if kind == "sighted" else "blind_decisions_*.json"
    rows = {}
    for f in sorted(glob.glob(str(LABELS / pattern))):
        for k, v in json.load(open(f, encoding="utf8")).items():
            rows[int(k)] = "not_anomaly" if v[0] == "false_positive" else v[0]
    if kind == "adjusted":  # сліпа розмітка, де є людська перевірка — рішення людини
        rows.update({int(k): v for k, v in json.load(open(LABELS / "human_labels.json", encoding="utf8")).items()})
    strata = {int(k): v for k, v in json.load(open(LABELS / "strata.json", encoding="utf8"))["strata"].items()}
    lab = pd.DataFrame({"item_id": list(rows), "status": list(rows.values())})
    lab = lab[lab["status"] != "needs_review"].copy()
    lab["y"] = (lab["status"] == "confirmed").astype(int)
    lab["stratum"] = lab["item_id"].map(strata)
    return lab.reset_index(drop=True)


def stratum_weights(lab: pd.DataFrame) -> pd.Series:
    """Ваги Горвіца–Томпсона: розмір страти в сукупності / розмічено в страті."""
    pop = pd.Series(json.load(open(LABELS / "strata.json", encoding="utf8"))["population"])
    return lab["stratum"].map(pop / lab["stratum"].value_counts()).to_numpy(float)


def scores(y: np.ndarray, pred: np.ndarray, score: np.ndarray, w: np.ndarray) -> dict:
    pred = pred.astype(bool)
    tp = (w * (pred & (y == 1))).sum()
    fp = (w * (pred & (y == 0))).sum()
    fn = (w * (~pred & (y == 1))).sum()
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": p,
        "recall": r,
        "f1": 2 * p * r / (p + r) if p + r else 0.0,
        "ap": average_precision_score(y, score, sample_weight=w),
    }


def budget_flags(score: pd.Series, analysed: pd.Series, share: float = BUDGET) -> pd.Series:
    """Позначити частку share позицій з найбільшим score серед проаналізованих."""
    s = score.where(analysed, -np.inf)
    k = max(1, int(round(share * analysed.sum())))
    thr = np.sort(s.to_numpy())[-k]
    return (s >= thr) & analysed


def _fit_predict(tr: pd.DataFrame, te: pd.DataFrame, seed: int) -> np.ndarray:
    return Calibrator.fit(tr, tr["y"].to_numpy(), random_state=seed).predict_proba(te)


def _best_threshold(y, prob, w) -> float:
    grid = np.linspace(0.2, 0.9, 29)
    f1 = [scores(y, prob >= t, prob, w)["f1"] for t in grid]
    return float(grid[int(np.argmax(f1))])


def nested_cv(lab: pd.DataFrame, w: np.ndarray, folds: int = 5, repeats: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Вкладена CV калібратора: (імовірність, рішення) для кожної позиції лише з моделей, які її не бачили.

    Поріг для зовнішнього фолду підбирається на внутрішній CV його навчальної частини (max зваженого F1).
    Неаналізовані позиції (замала група) отримують 0 і не позначаються.
    """
    ok = lab["analysed"].to_numpy()
    sub, wsub = lab[ok].reset_index(drop=True), w[ok]
    y = sub["y"].to_numpy()
    prob = np.zeros((repeats, len(sub)))
    flag = np.zeros((repeats, len(sub)))
    for rep in range(repeats):
        for tr, te in StratifiedKFold(folds, shuffle=True, random_state=rep).split(sub, y):
            inner = np.zeros(len(tr))
            for itr, ite in StratifiedKFold(folds, shuffle=True, random_state=100 + rep).split(tr, y[tr]):
                inner[ite] = _fit_predict(sub.iloc[tr[itr]], sub.iloc[tr[ite]], rep)
            t = _best_threshold(y[tr], inner, wsub[tr])
            p = _fit_predict(sub.iloc[tr], sub.iloc[te], rep)
            prob[rep, te], flag[rep, te] = p, p >= t
    out_p, out_f = np.zeros(len(lab)), np.zeros(len(lab), bool)
    out_p[ok] = prob.mean(axis=0)
    out_f[ok] = flag.mean(axis=0) >= 0.5  # рішення більшістю повторів
    return out_p, out_f


def stratified_bootstrap(lab: pd.DataFrame, fn, n: int = 2000, seed: int = 0) -> np.ndarray:
    """fn(індекси) → число; повторні вибірки з поверненням усередині кожної страти."""
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(lab["stratum"].to_numpy() == s) for s in lab["stratum"].unique()]
    out = np.empty(n)
    for b in range(n):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        out[b] = fn(idx)
    return out
