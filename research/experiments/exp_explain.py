"""Експеримент 3: якість пояснень (значення Шеплі, Монте-Карло за перестановками).

    cd backend && uv run python ../research/experiments/exp_explain.py

1. Точність: оцінка з 24 перестановками (як у системі) проти еталону з 2000 перестановок —
   середня абсолютна похибка в пунктах ризику, збіг трьох головних ознак, рангова кореляція.
2. Стабільність: 10 запусків з різними seed — збіг трьох головних ознак між запусками.
3. Ефективність (адитивність): |Σφ − (f(x) − E f(фон))| у пунктах ризику.
4. Вірність (deletion test): заміна k ознак з найбільшим |φ| на фонові значення має знижувати ризик
   сильніше, ніж заміна k випадкових ознак.
5. Глобальна важливість: середній |φ| по позначених позиціях.
"""

import time
from itertools import combinations

import numpy as np
import pandas as pd
from common import OUT, load_selection
from scipy.stats import spearmanr

from tendoor.ml.calibration import load_calibrator
from tendoor.ml.explain import FEATURE_LABELS, shapley_values
from tendoor.ml.pipeline import DetectionParams, run_detection

N_ITEMS = 120  # позначені позиції для аналізу (випадкова підвибірка)
REF_PERM = 2000
SYS_PERM = 24


def top3(phi_row: np.ndarray) -> set:
    return set(np.argsort(-np.abs(phi_row))[:3])


def main() -> None:
    cal = load_calibrator()
    df = load_selection()
    items = run_detection(df, DetectionParams()).items
    analysed = items[items["risk"].notna()]
    flagged = analysed[analysed["is_anomaly"]]
    normal = analysed[~analysed["is_anomaly"] & (analysed["risk"] < 30)]
    rng = np.random.default_rng(0)
    x = flagged.sample(min(N_ITEMS, len(flagged)), random_state=0)
    bg = normal.sample(100, random_state=42)
    print(f"позначено {len(flagged)}, аналіз {len(x)} позицій, фон {len(bg)}", flush=True)

    t = time.perf_counter()
    ref, base = shapley_values(cal, x, bg, n_permutations=REF_PERM, random_state=999)
    print(f"еталон: {time.perf_counter() - t:.0f} с", flush=True)
    runs = []
    t = time.perf_counter()
    for seed in range(10):
        runs.append(shapley_values(cal, x, bg, n_permutations=SYS_PERM, random_state=seed)[0])
    sec_per_item = (time.perf_counter() - t) / 10 / len(x)

    res = {}
    mae = np.mean([np.abs(r - ref).mean() for r in runs]) * 100
    top_ref = [len(top3(a) & top3(b)) / 3 for r in runs for a, b in zip(r, ref)]
    rho = np.mean([spearmanr(np.abs(a), np.abs(b))[0] for r in runs for a, b in zip(r, ref)])
    res["похибка φ проти еталону, пунктів ризику (MAE)"] = mae
    res["збіг топ-3 ознак з еталоном"] = float(np.mean(top_ref))
    res["рангова кореляція |φ| з еталоном (Спірмен)"] = float(rho)
    pair = [len(top3(a[i]) & top3(b[i])) / 3 for a, b in combinations(runs, 2) for i in range(len(x))]
    res["збіг топ-3 між запусками (10 seed)"] = float(np.mean(pair))
    res["час на позицію, мс"] = 1000 * sec_per_item

    prob = cal.predict_proba(x)
    gap = np.abs(ref.sum(axis=1) - (prob - base)) * 100
    res["порушення адитивності, пунктів (медіана)"] = float(np.median(gap))

    # deletion test: замінюємо ознаки середнім фону (по 100 фонових точках) і дивимося падіння ризику
    xs = x[cal.features].to_numpy(float)
    bgv = bg[cal.features].to_numpy(float)

    def risk_after(mask_cols: list[np.ndarray]) -> np.ndarray:
        out = np.zeros(len(xs))
        for b in bgv:
            z = xs.copy()
            for i, cols in enumerate(mask_cols):
                z[i, cols] = b[cols]
            out += cal.model.predict_proba(pd.DataFrame(z, columns=cal.features))[:, 1]
        return out / len(bgv)

    d = len(cal.features)
    sys_phi = runs[0]
    for k in (1, 2, 3):
        top = [np.argsort(-np.abs(r))[:k] for r in sys_phi]
        rnd = [rng.choice(d, size=k, replace=False) for _ in range(len(xs))]
        res[f"падіння ризику, топ-{k} за φ, пунктів"] = float(np.mean(prob - risk_after(top)) * 100)
        res[f"падіння ризику, {k} випадкових, пунктів"] = float(np.mean(prob - risk_after(rnd)) * 100)

    j = cal.features.index("text_dist")
    res["середній знаковий внесок text_dist, пунктів"] = float(ref[:, j].mean() * 100)
    res["частка позицій, де text_dist знижує ризик"] = float((ref[:, j] < 0).mean())
    out = pd.Series(res)
    print(out.round(3).to_string())
    out.round(4).to_csv(OUT / "explain.csv", encoding="utf-8-sig", header=["значення"])

    imp = pd.Series(np.abs(ref).mean(axis=0) * 100, index=cal.features).sort_values(ascending=False)
    imp = imp.rename(index=lambda f: f"{f} — {FEATURE_LABELS.get(f, f)}")
    print("\nглобальна важливість (середній |φ|, пункти ризику):")
    print(imp.round(2).to_string())
    imp.round(4).to_csv(OUT / "importance.csv", encoding="utf-8-sig", header=["mean_abs_phi_points"])


if __name__ == "__main__":
    main()
