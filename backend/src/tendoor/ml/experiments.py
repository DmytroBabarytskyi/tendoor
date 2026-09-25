"""Експеримент v1 → v2 на розмітці аудиторів і донавчання калібратора.

  python -m tendoor.ml.experiments --strata ../docs/notes/labels/strata.json [--save]

Розмітка стратифікована за рішенням v1 (топ-50, решта позначених, непозначені), тому метрики
на всю сукупність оцінюються з вагами Горвіца–Томпсона: вага позиції = розмір страти / розмічено в ній.
Калібратор оцінюється лише на відкладених фолдах крос-валідації.
"""

import argparse
import asyncio
import json
import warnings
from datetime import date

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold
from sqlalchemy import text

from tendoor.config import get_settings
from tendoor.infra.db import Databases
from tendoor.ml.calibration import FEATURES, Calibrator
from tendoor.ml.pipeline import DetectionParams, run_detection
from tendoor.repositories.sql.analysis import AnalysisFilters, SqlAnalysisRepository

REFERENCE = AnalysisFilters(("15",), date(2026, 8, 1), date(2026, 9, 30))


async def load(strata: dict[int, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    dbs = Databases(get_settings())
    df = await SqlAnalysisRepository(dbs.session_factory).load_selection(REFERENCE)
    async with dbs.session_factory() as s:
        rows = (
            await s.execute(text("SELECT item_id, status FROM verdict WHERE status <> 'needs_review'"))
        ).all()
    await dbs.close()
    labels = pd.DataFrame(rows, columns=["item_id", "status"])
    labels = labels[labels["item_id"].isin(strata)]
    labels["y"] = (labels["status"] == "confirmed").astype(int)
    labels["stratum"] = labels["item_id"].map(strata)
    return df, labels


def weighted_scores(y: np.ndarray, pred: np.ndarray, score: np.ndarray, w: np.ndarray) -> dict:
    tp, fp, fn = (w * (pred & (y == 1))).sum(), (w * (pred & (y == 0))).sum(), (w * (~pred & (y == 1))).sum()
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": p,
        "recall": r,
        "f1": 2 * p * r / (p + r) if p + r else 0.0,
        "ap": average_precision_score(y, score, sample_weight=w),
        "flagged_est": float((w * pred).sum()),
    }


def evaluate_run(
    df: pd.DataFrame, labels: pd.DataFrame, weights: pd.Series, params: DetectionParams
) -> tuple[dict, pd.DataFrame]:
    items = run_detection(df, params).items.set_index("item_id")
    lab = labels.set_index("item_id").join(items, how="left")
    # неаналізовані позиції (замала група) не позначені: підтверджена серед них — пропуск моделі
    lab["analysed"] = lab["risk"].notna()
    lab["is_anomaly"] = lab["is_anomaly"].fillna(False).astype(bool)
    lab["risk"] = lab["risk"].fillna(0.0)
    w = lab["stratum"].map(weights).to_numpy()
    return weighted_scores(
        lab["y"].to_numpy(), lab["is_anomaly"].to_numpy(bool), lab["risk"].to_numpy(), w
    ), lab


def oof_probabilities(lab: pd.DataFrame, folds: int = 5, repeats: int = 5) -> np.ndarray:
    """Імовірності на відкладених фолдах (усереднені за повторами); неаналізовані — 0."""
    y = lab["y"].to_numpy()
    ok = lab["analysed"].to_numpy()
    sub, ys = lab[ok], y[ok]
    probs = np.zeros((repeats, len(sub)))
    for rep in range(repeats):
        for tr, te in StratifiedKFold(folds, shuffle=True, random_state=rep).split(sub, ys):
            probs[rep, te] = Calibrator.fit(sub.iloc[tr], ys[tr], random_state=rep).predict_proba(
                sub.iloc[te]
            )
    prob = np.zeros(len(lab))
    prob[ok] = probs.mean(axis=0)
    return prob


def cross_validated(
    lab: pd.DataFrame, weights: pd.Series, folds: int = 5, repeats: int = 5
) -> tuple[dict, float]:
    """Імовірності калібратора на відкладених фолдах; поріг — максимум зваженого F1 на них."""
    y = lab["y"].to_numpy()
    w = lab["stratum"].map(weights).to_numpy()
    prob = oof_probabilities(lab, folds, repeats)
    grid = np.linspace(0.2, 0.9, 29)
    f1 = [weighted_scores(y, prob >= t, prob, w)["f1"] for t in grid]
    t_best = float(grid[int(np.argmax(f1))])
    return weighted_scores(y, prob >= t_best, prob, w), t_best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strata", required=True)
    parser.add_argument("--save", action="store_true", help="зберегти калібратор, навчений на всій розмітці")
    args = parser.parse_args()
    warnings.filterwarnings("ignore")
    with open(args.strata, encoding="utf8") as fh:
        meta = json.load(fh)
    strata = {int(k): v for k, v in meta["strata"].items()}
    df, labels = asyncio.run(load(strata))
    n = labels["stratum"].value_counts()
    weights = pd.Series(meta["population"]) / n
    print(f"вибірка: {len(df)} позицій; розмітка: {n.to_dict()} (підтверджено {labels['y'].sum()})")

    v1_text = dict(text_split_min=60, text_subgroup_min=10)  # параметри текстового поділу v1
    variants = {
        "v1": DetectionParams(pack_normalize=False, calibrate=False, **v1_text),
        "v1 + фасовка": DetectionParams(calibrate=False, **v1_text),
        "v1 + фасовка + дрібніший текстовий поділ": DetectionParams(
            calibrate=False, text_split_min=30, text_subgroup_min=5
        ),
    }
    rows, labs = [], {}
    for name, params in variants.items():
        scores, lab = evaluate_run(df, labels, weights, params)
        rows.append({"варіант": name, **scores})
        labs[name] = lab
    best_unsup = "v1 + фасовка + дрібніший текстовий поділ"  # база v2 (параметри за замовчуванням)
    cv, threshold = cross_validated(labs[best_unsup], weights)
    rows.append({"варіант": f"v2 = {best_unsup} + калібратор (CV)", **cv})
    table = pd.DataFrame(rows).set_index("варіант")
    print(table.round(3).to_string())
    print(f"поріг калібратора (CV, max F1): {threshold:.2f}")

    if args.save:
        lab = labs[best_unsup]
        lab = lab[lab["analysed"]]
        cal = Calibrator.fit(
            lab,
            lab["y"].to_numpy(),
            meta={
                "version": "v2-1",
                "trained_on": "запит №4 (CPV 15, 01.08–30.09.2026)",
                "n_labels": int(len(lab)),
                "n_positive": int(lab["y"].sum()),
                "threshold": threshold,
                "base": best_unsup,
                "cv": {k: round(float(v), 4) for k, v in cv.items()},
                "features": FEATURES,
            },
        )
        cal.save()
        print("калібратор збережено:", cal.meta)


if __name__ == "__main__":
    main()
