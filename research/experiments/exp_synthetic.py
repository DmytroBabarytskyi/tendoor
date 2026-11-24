"""Експеримент 2: синтетичні помилки, типові для Prozorro (відома істина), у двох категоріях ДК 021.

    cd backend && uv run python ../research/experiments/exp_synthetic.py

Типи вбудованих помилок (порівну, разом 3 % позицій):
  moderate  — помірне відхилення ціни: ×2, ×3, ×0,4, ×0,5;
  strong    — сильне відхилення: ×5, ×10, ×0,1, ×0,2;
  unit      — масштаб одиниці (грам/кілограм, кг/тонна): ×1000 або ×0,001;
  lot_total — сума лоту записана як ціна за одиницю: ×обсяг (лише позиції з обсягом ≥ 5).
Категорія 15 (харчові продукти) — та, на розмітці якої навчено калібратор; 03 (сільськогосподарська
продукція) — поза навчанням: перевірка перенесення без донавчання.
Справжні аномалії в даних не мають міток, тож precision — нижня оцінка; recall за типами точний.
"""

from datetime import date

import numpy as np
import pandas as pd
from common import OUT, budget_flags, load_selection
from sklearn.metrics import average_precision_score

from baselines import iqr_score, per_group, sigma3_score
from tendoor.ml.calibration import load_calibrator
from tendoor.ml.pipeline import DetectionParams, run_detection
from tendoor.repositories.sql.analysis import AnalysisFilters

RATE = 0.03
SEEDS = (0, 1, 2)
TYPES = ("moderate", "strong", "unit", "lot_total")
DOMAINS = {
    "15 Харчові продукти": AnalysisFilters(("15",), date(2026, 8, 1), date(2026, 9, 30)),
    "03 Сільськогосподарська продукція": AnalysisFilters(("03",), date(2026, 8, 1), date(2026, 9, 30)),
}
V1 = DetectionParams(pack_normalize=False, calibrate=False, text_split_min=60, text_subgroup_min=10)
V2_STAGE1 = DetectionParams(calibrate=False)
CALIBRATORS = {
    "калібратор на першій розмітці (з рішеннями v1)": load_calibrator(OUT / "calibrator_deployed_old.joblib"),
    "калібратор на сліпій розмітці, монотонний": load_calibrator(OUT / "calibrator_blind.joblib"),
    "калібратор на сліпій + людській, монотонний": load_calibrator(OUT / "calibrator_adjusted.joblib"),
}


def inject(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    """Копія вибірки з вбудованими помилками; мітка — тип помилки або None."""
    rng = np.random.default_rng(seed)
    out = df.copy().reset_index(drop=True)
    out["unit_price_base"] = out["unit_price_base"].astype(float)
    qty = out["quantity_base"].astype(float)
    kind = pd.Series(None, index=out.index, dtype=object)
    n = int(len(out) * RATE / len(TYPES))
    free = np.ones(len(out), bool)
    for t in TYPES:
        pool = np.flatnonzero(free & ((qty >= 5).to_numpy() if t == "lot_total" else True))
        idx = rng.choice(pool, size=n, replace=False)
        free[idx] = False
        if t == "moderate":
            f = rng.choice([2.0, 3.0, 0.4, 0.5], size=n)
        elif t == "strong":
            f = rng.choice([5.0, 10.0, 0.1, 0.2], size=n)
        elif t == "unit":
            f = rng.choice([1000.0, 0.001], size=n)
        else:
            f = qty.iloc[idx].to_numpy()
        out.loc[idx, "unit_price_base"] *= f
        kind.iloc[idx] = t
    return out, kind


def evaluate(name: str, kind: pd.Series, pred: pd.Series, score: pd.Series) -> dict:
    truth = kind.notna()
    pred = pred.reindex(kind.index).fillna(False).astype(bool)
    score = score.reindex(kind.index).fillna(score.min() - 1)
    tp, fp = (pred & truth).sum(), (pred & ~truth).sum()
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / truth.sum()
    row = {"метод": name, "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
           "ap": average_precision_score(truth, score), "позначено, %": 100 * pred.mean()}
    for t in TYPES:
        m = kind == t
        row[f"recall {t}"] = (pred & m).sum() / m.sum()
    return row


def main() -> None:
    rows = []
    for domain, filters in DOMAINS.items():
        base = load_selection(filters)
        base = base[(base["unit_price_base"].astype(float) > 0) & (base["quantity_base"].astype(float) > 0)]
        print(f"{domain}: {len(base)} позицій", flush=True)
        for seed in SEEDS:
            data, kind = inject(base, seed)
            all_items = pd.Series(True, index=data.index)
            s3 = sigma3_score(data)
            iq = iqr_score(data, cpv_digits=8)
            res = []
            res.append(evaluate("3σ, клас ДК 021", kind, s3 > 3, s3))
            res.append(evaluate("IQR, код ДК 021", kind, iq > 1.5, iq))
            v1 = run_detection(data, V1).items.set_index(data.index)
            v2 = run_detection(data, V2_STAGE1).items.set_index(data.index)  # перший етап + ознаки
            analysed = v2["risk"].notna()
            lp = np.log(v2.loc[analysed, "price"].astype(float))
            ifs = per_group(lp, v2.loc[analysed, "group"], "iforest").reindex(data.index)
            res.append(evaluate("v1", kind, v1["is_anomaly"], v1["risk"]))
            res.append(evaluate("перший етап v2", kind, v2["rule_anomaly"], v2["robust_z"].abs()))
            extreme = v2["is_extreme"].fillna(0).astype(float) > 0
            share = None
            for cname, cal in CALIBRATORS.items():
                prob = pd.Series(np.nan, index=data.index)
                prob[analysed] = cal.predict_proba(v2.loc[analysed])
                flag = (prob >= cal.meta.get("threshold", 0.5)) & analysed
                res.append(evaluate(f"v2, {cname}", kind, flag, prob))
                res.append(evaluate(f"гібрид, {cname}", kind, flag | extreme, prob.fillna(0) + extreme))
                share = share or float(flag.mean())
            # Isolation Forest з тим самим бюджетом тривог, що й v2 з розгорнутим калібратором
            res.append(evaluate("Isolation Forest у групах (бюджет v2)", kind,
                                budget_flags(ifs.fillna(-1), analysed, share), ifs))
            for r in res:
                rows.append({"категорія": domain, "seed": seed, **r})
            print(f"  seed {seed} готово", flush=True)
    t = pd.DataFrame(rows).drop(columns="seed").groupby(["категорія", "метод"], sort=False).mean()
    pd.set_option("display.width", 250)
    print(t.round(3).to_string())
    t.round(4).to_csv(OUT / "synthetic.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
