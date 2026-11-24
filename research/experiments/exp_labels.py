"""Експеримент 1: якість на стратифікованій розмітці (ваги Горвіца–Томпсона).

    cd backend && uv run python ../research/experiments/exp_labels.py [blind|sighted]

Порівнюються: статистичні правила, некеровані детектори (у групах конвеєра й у просторі ознак),
перший етап конвеєра (v1 і абляції) та двоетапний конвеєр v2 (калібратор, вкладена CV).
Некеровані методи порівнюються за однакового бюджету тривог (BUDGET позицій) і за AP.
"""

import sys

import numpy as np
import pandas as pd
from common import (
    BUDGET,
    OUT,
    budget_flags,
    load_labels,
    load_selection,
    nested_cv,
    scores,
    stratified_bootstrap,
    stratum_weights,
)

from baselines import global_detector, iqr_score, per_group, sigma3_score
from tendoor.ml.calibration import FEATURES
from tendoor.ml.pipeline import DetectionParams, run_detection

KIND = sys.argv[1] if len(sys.argv) > 1 else "blind"
V1_TEXT = dict(text_split_min=60, text_subgroup_min=10)
STAGE1 = {
    "v1 (перший етап, як у v1)": DetectionParams(pack_normalize=False, calibrate=False, **V1_TEXT),
    "+ перерахунок фасовки": DetectionParams(calibrate=False, **V1_TEXT),
    "+ дрібніший текстовий поділ (перший етап v2)": DetectionParams(calibrate=False),
    "перший етап v2 без групування за ДК 021": DetectionParams(calibrate=False, cpv_grouping=False),
    "перший етап v2 без текстового поділу": DetectionParams(calibrate=False, text_split=False),
}
V2_BASE = "+ дрібніший текстовий поділ (перший етап v2)"


def main() -> None:
    df = load_selection()
    lab = load_labels(KIND)
    w = stratum_weights(lab)
    df = df.set_index("item_id", drop=False)
    print(f"вибірка {len(df)} позицій; мітки ({KIND}): {lab['stratum'].value_counts().to_dict()}, "
          f"підтверджено {lab['y'].sum()}")
    y = lab["y"].to_numpy()
    ids = lab["item_id"]
    rows: list[dict] = []

    def add(name: str, family: str, pred: pd.Series, score: pd.Series) -> None:
        p = pred.reindex(ids).fillna(False).to_numpy(bool)
        s = score.reindex(ids).fillna(-np.inf).replace(-np.inf, -1e9).to_numpy(float)
        rows.append({"метод": name, "тип": family, **scores(y, p, s, w)})

    all_items = pd.Series(True, index=df.index)
    # 1) статистичні правила: як аудитор без системи (клас ДК 021 + одиниця)
    for name, s, thr in (
        ("3σ, клас ДК 021", sigma3_score(df), 3.0),
        ("IQR (Тьюкі), клас ДК 021", iqr_score(df), 1.5),
        ("IQR (Тьюкі), код ДК 021", iqr_score(df, cpv_digits=8), 1.5),
    ):
        add(name + " — власний поріг", "правило", s > thr, s)
        add(name + f" — бюджет {BUDGET:.0%}", "правило", budget_flags(s, all_items), s)

    # 2) перший етап конвеєра та абляції
    runs = {}
    for name, params in STAGE1.items():
        items = run_detection(df.reset_index(drop=True), params).items.set_index("item_id")
        runs[name] = items
        analysed = items["risk"].notna()
        add(name + " — власний поріг", "конвеєр", items["is_anomaly"], items["risk"])
        add(name + f" — бюджет {BUDGET:.0%}", "конвеєр", budget_flags(items["risk"], analysed), items["risk"])

    base = runs[V2_BASE]
    analysed = base["risk"].notna()
    # 3) некеровані детектори в тих самих групах (одновимірно, log-ціна після фасовки)
    lp = np.log(base.loc[analysed, "price"].astype(float))
    for m, title in (("iforest", "Isolation Forest"), ("lof", "LOF"), ("ecod", "ECOD")):
        s = per_group(lp, base.loc[analysed, "group"], m).reindex(base.index)
        add(f"{title} у групах конвеєра — бюджет {BUDGET:.0%}", "некерований", budget_flags(s.fillna(-1), analysed), s)
    # 4) некеровані детектори в просторі 19 ознак калібратора (без розмітки)
    x = base.loc[analysed, FEATURES].astype(float)
    for m, title in (("iforest", "Isolation Forest"), ("ecod", "ECOD")):
        s = global_detector(x, m).reindex(base.index)
        add(f"{title} на ознаках калібратора — бюджет {BUDGET:.0%}", "некерований", budget_flags(s.fillna(-1e9), analysed), s)

    # 5) v2: калібратор на вердиктах, вкладена CV
    lab2 = lab.join(base, on="item_id")
    lab2["analysed"] = lab2["risk"].notna()
    prob, flag = nested_cv(lab2, w)
    rows.append({"метод": "v2: перший етап + калібратор (вкладена CV)", "тип": "конвеєр", **scores(y, flag, prob, w)})
    # гібрид: грубі відхилення першого етапу (екстремуми за 3·IQR) позначаються завжди, решту ранжує калібратор
    extreme = lab2["is_extreme"].fillna(0).astype(float).to_numpy() > 0
    h_flag, h_score = flag | extreme, prob + extreme
    rows.append({"метод": "гібрид: екстремуми завжди + калібратор (вкладена CV)", "тип": "конвеєр",
                 **scores(y, h_flag, h_score, w)})

    table = pd.DataFrame(rows).set_index("метод")
    pd.set_option("display.width", 200)
    print(table.round(3).to_string())
    table.round(4).to_csv(OUT / f"labels_{KIND}.csv", encoding="utf-8-sig")

    # бутстреп різниць: v2 проти v1 і проти найкращого базового за AP
    v1 = runs["v1 (перший етап, як у v1)"].reindex(ids)
    v1_flag = v1["is_anomaly"].fillna(False).to_numpy(bool)
    v1_score = v1["risk"].fillna(-1).to_numpy(float)

    def diff(metric, a_pred, a_score, b_pred, b_score):
        def fn(idx):
            return (scores(y[idx], a_pred[idx], a_score[idx], w[idx])[metric]
                    - scores(y[idx], b_pred[idx], b_score[idx], w[idx])[metric])
        return fn

    report = {}
    for metric in ("f1", "ap"):
        b = stratified_bootstrap(lab, diff(metric, flag, prob, v1_flag, v1_score))
        report[f"v2 − v1, {metric}"] = (b.mean(), *np.percentile(b, [2.5, 97.5]), (b <= 0).mean())
        b = stratified_bootstrap(lab, diff(metric, h_flag, h_score, v1_flag, v1_score))
        report[f"гібрид − v1, {metric}"] = (b.mean(), *np.percentile(b, [2.5, 97.5]), (b <= 0).mean())
        b = stratified_bootstrap(lab, diff(metric, h_flag, h_score, flag, prob))
        report[f"гібрид − v2, {metric}"] = (b.mean(), *np.percentile(b, [2.5, 97.5]), (b <= 0).mean())
    best = table[table["тип"] != "конвеєр"]["ap"].idxmax()
    print("найкращий базовий за AP:", best)
    rep_df = pd.DataFrame(report, index=["середнє", "2,5 %", "97,5 %", "P(≤0)"]).T
    print(rep_df.round(3).to_string())
    rep_df.round(4).to_csv(OUT / f"bootstrap_{KIND}.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
